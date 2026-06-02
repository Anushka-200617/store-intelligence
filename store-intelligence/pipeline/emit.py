"""
Event schema + emission helpers.
Single source of truth for the event JSON structure.
"""
import json
import uuid
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class _SafeEncoder(json.JSONEncoder):
    """Handles numpy types that standard json cannot serialise."""
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super().default(obj)


def new_event(
    store_id:    str,
    camera_id:   str,
    visitor_id:  str,
    event_type:  str,
    timestamp:   datetime,
    confidence:  float,
    zone_id:     Optional[str] = None,
    dwell_ms:    int           = 0,
    is_staff:    bool          = False,
    queue_depth: Optional[int] = None,
    sku_zone:    Optional[str] = None,
    session_seq: Optional[int] = None,
) -> dict:
    """Build a schema-compliant event dict."""
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "zone_id":    zone_id,
        "dwell_ms":   int(dwell_ms),
        "is_staff":   bool(is_staff),      # force Python bool, never numpy bool_
        "confidence": round(float(confidence), 4),
        "metadata": {
            "queue_depth": int(queue_depth) if queue_depth is not None else None,
            "sku_zone":    sku_zone,
            "session_seq": int(session_seq) if session_seq is not None else None,
        },
    }


def write_events(events: list[dict], output_path: Path) -> None:
    """Append events to a JSONL file (one event per line)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a") as f:
        for ev in events:
            f.write(json.dumps(ev, cls=_SafeEncoder) + "\n")