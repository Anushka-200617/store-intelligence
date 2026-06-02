"""
Optimized staff detection using behavioural patterns + POS data.

Strategy:
1. POS transaction window on billing cam → high-confidence staff
2. Dwell time analysis → customers dwell 30+ sec per zone; staff pass through
3. Movement pattern → staff visit 3+ zones in <2 min; customers stay linear
4. Zone entry-exit ratio → staff: enter many zones; customers: visit 1-2 zones
"""
from collections import defaultdict
from datetime import datetime
from typing import Optional
import numpy as np


class VisitorTracker:
    """
    Advanced tracking with behavioural staff detection.
    """
    MIN_CONF_FOR_ENTRY = 0.65
    OCCLUSION_S        = 8
    REENTRY_S          = 90
    EDGE_FILTER_X      = 0.85

    # Staff behaviour thresholds
    STAFF_DWELL_MAX_MS = 5000        # staff don't dwell >5sec per zone
    STAFF_ZONE_COUNT   = 3           # staff visit 3+ zones quickly
    CUSTOMER_DWELL_MIN_MS = 10000    # customers dwell 10+ sec

    def __init__(self):
        self._active:         dict = {}  # track_id → visitor info
        self._exited:         dict = {}
        self._seq:            dict = defaultdict(int)
        self._entry_count:    int  = 0
        self._seen_vids:      set  = set()
        self._zone_history:   dict = defaultdict(list)  # visitor_id → [(zone, time), ...]
        self._dwell_times:    dict = defaultdict(dict)  # visitor_id → {zone: total_ms}

    def get_or_create(self, track_id, entry_time, cx=0.5, cy=0.5, conf=0.0):
        """Returns (vid, is_reentry, should_emit_entry)."""
        
        if cx > self.EDGE_FILTER_X:
            return f"REFLECTION_{track_id}", False, False

        if track_id in self._active:
            info = self._active[track_id]
            info["last_cx"] = cx
            info["last_cy"] = cy
            info["last_time"] = entry_time
            return info["vid"], False, False

        # Check for occlusion recovery
        best_vid, best_score, best_info = None, float("inf"), None
        for vid, info in list(self._exited.items()):
            delta = (entry_time - info["time"]).total_seconds()
            pos_dist = ((cx - info["cx"])**2 + (cy - info["cy"])**2) ** 0.5
            
            if delta < self.OCCLUSION_S and pos_dist < 0.25:
                # Occlusion recovery — save info before deleting
                best_info = info
                best_vid = vid
                del self._exited[vid]
                self._active[track_id] = {
                    "vid": vid, "last_cx": cx, "last_cy": cy,
                    "last_time": entry_time, "entry_time": best_info["entry_time"],
                    "is_staff": best_info.get("is_staff", False),
                }
                self._seq[vid] += 1
                return vid, False, False

            if self.OCCLUSION_S <= delta <= self.REENTRY_S:
                if delta < best_score:
                    best_vid, best_score, best_info = vid, delta, info

        if best_vid:
            # Save info before deleting
            saved_info = dict(best_info)
            del self._exited[best_vid]
            self._active[track_id] = {
                "vid": best_vid, "last_cx": cx, "last_cy": cy,
                "last_time": entry_time, "entry_time": saved_info["entry_time"],
                "is_staff": saved_info.get("is_staff", False),
            }
            should_emit = conf >= self.MIN_CONF_FOR_ENTRY
            return best_vid, True, should_emit

        # New visitor
        self._entry_count += 1
        vid = f"VIS_{self._entry_count:05d}"
        self._seen_vids.add(vid)
        self._active[track_id] = {
            "vid": vid, "last_cx": cx, "last_cy": cy,
            "last_time": entry_time, "entry_time": entry_time,
            "is_staff": False,  # Default to customer; will be updated based on behaviour
        }
        should_emit = conf >= self.MIN_CONF_FOR_ENTRY
        return vid, False, should_emit

    def on_exit(self, track_id, exit_time):
        info = self._active.pop(track_id, None)
        if info and not info["vid"].startswith("REFLECTION"):
            self._exited[info["vid"]] = {
                "time": exit_time, "cx": info["last_cx"], "cy": info["last_cy"],
                "entry_time": info["entry_time"],
                "is_staff": info.get("is_staff", False),
            }
            return info["vid"]
        return None

    def record_zone_visit(self, visitor_id: str, zone_id: str, enter_time: datetime, exit_time: datetime):
        """Record a zone visit for staff detection analysis."""
        if not zone_id:
            return
        dwell_ms = int((exit_time - enter_time).total_seconds() * 1000)
        self._zone_history[visitor_id].append((zone_id, enter_time, dwell_ms))
        self._dwell_times[visitor_id][zone_id] = self._dwell_times[visitor_id].get(zone_id, 0) + dwell_ms

    def classify_staff(self, visitor_id: str, frame_time: datetime = None, camera_id: str = "", 
                      billing_flag: bool = False) -> bool:
        """
        Classify as staff based on behaviour patterns.
        Returns True if likely staff, False if likely customer.
        """
        # Rule 1: Billing camera during POS transaction → staff
        if billing_flag and camera_id == "CAM_BILLING_01":
            return True

        history = self._zone_history.get(visitor_id, [])
        dwell = self._dwell_times.get(visitor_id, {})

        if not history:
            return False  # No zone history = customer (hasn't moved much)

        # Rule 2: Visit many zones rapidly → staff
        unique_zones = len(set(z[0] for z in history))
        if unique_zones >= self.STAFF_ZONE_COUNT:
            if len(history) >= 3:
                first_time = history[0][1]
                last_time = history[-1][1]
                elapsed_s = (last_time - first_time).total_seconds()
                if elapsed_s < 120 and unique_zones >= 3:
                    return True

        # Rule 3: Never dwells long in any zone → staff
        has_long_dwell = any(ms >= self.CUSTOMER_DWELL_MIN_MS for ms in dwell.values())
        if not has_long_dwell and len(history) >= 3:
            return True

        # Rule 4: Avg dwell per zone is very short → staff
        if history:
            avg_dwell = sum(z[2] for z in history) / len(history)
            if avg_dwell < self.STAFF_DWELL_MAX_MS and len(history) >= 5:
                return True

        # Default: customer
        return False

    def next_seq(self, vid):
        self._seq[vid] += 1
        return self._seq[vid]

    @property
    def unique_visitors(self):
        return len(self._seen_vids)