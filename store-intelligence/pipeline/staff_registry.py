"""
Staff registry for ST1008 — Brigade Bangalore.
Built directly from pos_transactions CSV.

Used by detect.py to:
1. Flag billing camera detections during transaction windows as staff
2. Help calibrate staff zone positions on floor cameras
"""
from datetime import datetime, timezone

# ── Known staff from POS data ─────────────────────────────────────
STAFF = {
    1178: "kasthuri v",
    971:  "Zufishan Khazra",
    523:  "Shashikala",
    737:  "Naziya Begum",
    1190: "Priya v",
}
STAFF_IDS = set(STAFF.keys())

# ── Transaction windows (IST times from POS CSV) ──────────────────
# Each transaction = staff was at billing counter at this time
# Used to identify staff in billing camera footage
TRANSACTION_WINDOWS_IST = [
    {"time": "12:15:05", "salesperson_id": 1178, "name": "kasthuri v"},
    {"time": "12:42:18", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "13:41:55", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "13:55:16", "salesperson_id": 0,    "name": "Zufishan Khazra"},
    {"time": "14:23:21", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "15:02:20", "salesperson_id": 1190, "name": "Priya v"},
    {"time": "15:46:39", "salesperson_id": 1178, "name": "kasthuri v"},
    {"time": "15:50:44", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "16:08:03", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "16:45:32", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "16:55:36", "salesperson_id": 1178, "name": "kasthuri v"},
    {"time": "17:44:44", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "17:55:02", "salesperson_id": 1190, "name": "Priya v"},
    {"time": "18:00:18", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "18:07:14", "salesperson_id": 1178, "name": "kasthuri v"},
    {"time": "18:41:51", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "19:02:09", "salesperson_id": 737,  "name": "Naziya Begum"},
    {"time": "19:21:55", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "19:33:52", "salesperson_id": 737,  "name": "Naziya Begum"},
    {"time": "19:41:29", "salesperson_id": 1178, "name": "kasthuri v"},
    {"time": "19:54:02", "salesperson_id": 1190, "name": "Priya v"},
    {"time": "20:25:04", "salesperson_id": 971,  "name": "Zufishan Khazra"},
    {"time": "21:16:15", "salesperson_id": 523,  "name": "Shashikala"},
    {"time": "21:39:55", "salesperson_id": 523,  "name": "Shashikala"},
]

# ── Who was on the floor during clip window (20:09-20:11 IST) ─────
# Last transaction before clip: 19:54 (Priya v / 1190)
# Next transaction after clip : 20:25 (Zufishan / 971)
# So during the clip, Priya and Zufishan were likely on the floor
ACTIVE_STAFF_DURING_CLIP = {971, 1190}


def is_transaction_window(frame_time_utc: datetime,
                           window_minutes: int = 5) -> bool:
    """
    Returns True if frame_time is within `window_minutes` of any
    POS transaction. Used to identify billing counter staff.

    frame_time_utc: UTC datetime from clip timestamp
    """
    # Convert UTC to IST for comparison
    ist_offset_s = 5 * 3600 + 30 * 60
    frame_ist    = frame_time_utc.timestamp() + ist_offset_s
    frame_dt     = datetime.fromtimestamp(frame_ist)

    for txn in TRANSACTION_WINDOWS_IST:
        h, m, s  = txn["time"].split(":")
        txn_secs = int(h) * 3600 + int(m) * 60 + int(s)
        frame_secs = frame_dt.hour * 3600 + frame_dt.minute * 60 + frame_dt.second
        if abs(frame_secs - txn_secs) <= window_minutes * 60:
            return True
    return False


def get_active_staff_name(frame_time_utc: datetime) -> str:
    """Returns name of staff member most likely active at this time."""
    ist_offset_s = 5 * 3600 + 30 * 60
    frame_ist    = frame_time_utc.timestamp() + ist_offset_s
    frame_dt     = datetime.fromtimestamp(frame_ist)
    frame_secs   = frame_dt.hour * 3600 + frame_dt.minute * 60 + frame_dt.second

    closest      = None
    closest_diff = float("inf")
    for txn in TRANSACTION_WINDOWS_IST:
        h, m, s  = txn["time"].split(":")
        txn_secs = int(h) * 3600 + int(m) * 60 + int(s)
        diff     = abs(frame_secs - txn_secs)
        if diff < closest_diff:
            closest_diff = diff
            closest      = txn["name"]
    return closest or "unknown"