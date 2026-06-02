"""
Detection + tracking with behavioural staff analysis.
Uses dwell time, zone transitions, and POS data to identify staff.
"""
import argparse
import cv2
import json
from datetime import datetime, timedelta
from pathlib import Path

from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

from tracker import VisitorTracker
from emit import new_event, write_events

FRAME_SKIP       = 3
CONF_THRESH      = 0.35
PERSON_CLASS     = 0
DWELL_EMIT_MS    = 30_000

BILLING_CAM_IDS  = {"CAM_BILLING_01"}
FLOOR_CAM_IDS    = {"CAM_FLOOR_SKINCARE", "CAM_FLOOR_MAKEUP"}

BILLING_CUSTOMER_Y = 0.45


def load_zone_map(layout_path, store_id, camera_id):
    try:
        with open(layout_path) as f:
            layout = json.load(f)
        store = next((s for s in layout if s["store_id"] == store_id), None)
        if store:
            return {z["zone_id"]: z["polygon"] for z in store.get("zones", [])
                    if z.get("camera_id") == camera_id}
    except Exception as e:
        print(f"  [WARN] Zone map: {e}")
    return {}


def point_in_zone(cx, cy, poly):
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > cy) != (yj > cy)) and (cx < (xj-xi)*(cy-yi)/(yj-yi)+xi):
            inside = not inside
        j = i
    return inside


def get_zone(cx, cy, zone_map):
    for zid, poly in zone_map.items():
        if point_in_zone(cx, cy, poly):
            return zid
    return None


def run(clip_path, store_id, camera_id, clip_start, output_path, store_layout=None):
    is_billing = camera_id in BILLING_CAM_IDS
    is_floor   = camera_id in FLOOR_CAM_IDS

    cam_type = "BILLING" if is_billing else "FLOOR" if is_floor else "ENTRY"
    print(f"\n  Camera: {camera_id}  Type: {cam_type}")
    print(f"  Loading YOLOv8n...")

    model    = YOLO("yolov8n.pt")
    tracker  = DeepSort(max_age=40, n_init=3, max_iou_distance=0.7)
    vtracker = VisitorTracker()

    zone_map = load_zone_map(store_layout, store_id, camera_id) if store_layout else {}
    print(f"  Zones: {list(zone_map.keys()) or ['(full frame)']}")

    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        print(f"  [ERROR] Cannot open: {clip_path}")
        return

    fps          = cap.get(cv2.CAP_PROP_FPS) or 15.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"  FPS={fps:.0f}  Frames={total_frames}  Duration={total_frames/fps:.0f}s")

    frame_idx     = 0
    total_dets    = 0
    events_buffer = []
    track_state   = {}

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % FRAME_SKIP != 0:
            continue

        H, W       = frame.shape[:2]
        frame_time = clip_start + timedelta(milliseconds=(frame_idx / fps) * 1000)

        results    = model(frame, classes=[PERSON_CLASS], conf=CONF_THRESH, verbose=False)
        detections = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            detections.append(([x1, y1, x2-x1, y2-y1], conf, "person"))
        total_dets += len(detections)

        tracks     = tracker.update_tracks(detections, frame=frame)
        active_ids = set()

        for track in tracks:
            if not track.is_confirmed():
                continue

            tid  = track.track_id
            ltrb = track.to_ltrb()
            x1 = max(0, int(ltrb[0])); y1 = max(0, int(ltrb[1]))
            x2 = min(W, int(ltrb[2])); y2 = min(H, int(ltrb[3]))
            if x2 <= x1 or y2 <= y1:
                continue

            cx      = ((x1+x2)/2) / W
            cy      = ((y1+y2)/2) / H
            conf    = track.det_conf or 0.5

            active_ids.add(tid)

            if tid not in track_state:
                vid, is_reentry, should_emit = vtracker.get_or_create(tid, frame_time, cx, cy, conf)
                track_state[tid] = {
                    "vid": vid, "zone": None, "zone_enter_time": None,
                    "last_dwell_emit": None, "entered": False,
                }

                if should_emit:
                    if is_floor or is_billing:
                        track_state[tid]["entered"] = True
                        ev_type = "REENTRY" if is_reentry else "ENTRY"
                        seq = vtracker.next_seq(vid)
                        events_buffer.append(new_event(
                            store_id, camera_id, vid, ev_type,
                            frame_time, conf, is_staff=False, session_seq=seq,
                        ))
                        print(f"    [{ev_type}] {vid} conf={conf:.2f}")

            state = track_state[tid]
            if not state["entered"]:
                continue

            cur_zone  = get_zone(cx, cy, zone_map)
            prev_zone = state["zone"]

            if cur_zone != prev_zone:
                if prev_zone and state["zone_enter_time"]:
                    # Record dwell for staff analysis
                    vtracker.record_zone_visit(state["vid"], prev_zone,
                                               state["zone_enter_time"], frame_time)
                    seq = vtracker.next_seq(state["vid"])
                    events_buffer.append(new_event(
                        store_id, camera_id, state["vid"], "ZONE_EXIT",
                        frame_time, conf, zone_id=prev_zone,
                        is_staff=False, session_seq=seq,
                    ))

                if cur_zone:
                    state["zone_enter_time"] = frame_time
                    state["last_dwell_emit"] = frame_time
                    seq = vtracker.next_seq(state["vid"])
                    
                    # Check for billing queue
                    if cur_zone == "BILLING":
                        events_buffer.append(new_event(
                            store_id, camera_id, state["vid"],
                            "BILLING_QUEUE_JOIN", frame_time, conf,
                            zone_id="BILLING", is_staff=False, session_seq=seq,
                        ))
                    else:
                        events_buffer.append(new_event(
                            store_id, camera_id, state["vid"], "ZONE_ENTER",
                            frame_time, conf, zone_id=cur_zone,
                            is_staff=False, session_seq=seq,
                        ))
                state["zone"] = cur_zone

            # ZONE_DWELL
            if (state["zone"] and state["last_dwell_emit"] and
                    (frame_time - state["last_dwell_emit"]).total_seconds()*1000 >= DWELL_EMIT_MS):
                dwell_ms = int((frame_time - state["zone_enter_time"]).total_seconds()*1000)
                seq = vtracker.next_seq(state["vid"])
                events_buffer.append(new_event(
                    store_id, camera_id, state["vid"], "ZONE_DWELL",
                    frame_time, conf, zone_id=state["zone"],
                    dwell_ms=dwell_ms, is_staff=False, session_seq=seq,
                ))
                state["last_dwell_emit"] = frame_time

        # Lost tracks → EXIT
        for tid in set(track_state.keys()) - active_ids:
            state = track_state.pop(tid)
            if not state["entered"]:
                continue
            vid = vtracker.on_exit(tid, frame_time)
            if vid:
                # Classify as staff based on behaviour
                is_staff = vtracker.classify_staff(vid, frame_time, camera_id,
                                                   billing_flag=(is_billing))
                seq = vtracker.next_seq(vid)
                if is_billing and state["zone"] == "BILLING":
                    events_buffer.append(new_event(
                        store_id, camera_id, vid, "BILLING_QUEUE_ABANDON",
                        frame_time, 0.5, zone_id="BILLING",
                        is_staff=is_staff, session_seq=seq,
                    ))
                else:
                    events_buffer.append(new_event(
                        store_id, camera_id, vid, "EXIT",
                        frame_time, 0.5, is_staff=is_staff, session_seq=seq,
                    ))
                if is_staff:
                    print(f"    [STAFF]   {vid} → {len(vtracker._zone_history[vid])} zone visits")

        if len(events_buffer) >= 500:
            write_events(events_buffer, output_path)
            events_buffer.clear()

    cap.release()
    if events_buffer:
        write_events(events_buffer, output_path)

    event_count = 0
    event_types = {}
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event_count += 1
                try:
                    et = json.loads(line).get("event_type", "?")
                    event_types[et] = event_types.get(et, 0) + 1
                except Exception:
                    pass

    print(f"\n  ── Summary ──────────────────────────────────────")
    print(f"  Total detections  : {total_dets}")
    print(f"  Unique visitors   : {vtracker.unique_visitors}")
    print(f"  Events in file    : {event_count}")
    for et, cnt in sorted(event_types.items()):
        print(f"    {et:<35} {cnt}")
    print(f"  ─────────────────────────────────────────────────\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", required=True)
    parser.add_argument("--store-id", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--clip-start", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--store-layout", default=None)
    args = parser.parse_args()

    clip_start = datetime.fromisoformat(args.clip_start.replace("Z", "+00:00"))
    run(args.clip, args.store_id, args.camera_id, clip_start, Path(args.output), args.store_layout)