"""GET /stores/{store_id}/anomalies — Queue spike, conversion drop, dead zone."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import StoreEvent

router = APIRouter(prefix="/stores", tags=["anomalies"])

QUEUE_SPIKE_THRESHOLD = 5
DEAD_ZONE_MINUTES     = 30

@router.get("/{store_id}/anomalies")
def get_anomalies(store_id: str, db: Session = Depends(get_db)):
    try:
        now = datetime.now(timezone.utc)
        anomalies = []

        # 1. Queue spike
        latest_queue = (
            db.query(StoreEvent.queue_depth, StoreEvent.timestamp)
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "BILLING_QUEUE_JOIN")
            .order_by(StoreEvent.timestamp.desc()).first()
        )
        if latest_queue and (latest_queue.queue_depth or 0) >= QUEUE_SPIKE_THRESHOLD:
            anomalies.append({
                "type": "BILLING_QUEUE_SPIKE",
                "severity": "CRITICAL" if latest_queue.queue_depth >= 8 else "WARN",
                "detail": f"Queue depth {latest_queue.queue_depth} at billing counter",
                "suggested_action": "Open additional billing counter or redirect floor staff",
                "detected_at": latest_queue.timestamp.isoformat(),
            })

        # 2. Dead zones (no visits in last 30 min)
        zone_last_visit = (
            db.query(StoreEvent.zone_id, func.max(StoreEvent.timestamp).label("last_visit"))
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "ZONE_ENTER",
                    StoreEvent.is_staff == False)
            .group_by(StoreEvent.zone_id).all()
        )
        for row in zone_last_visit:
            last = row.last_visit
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last and (now - last).total_seconds() > DEAD_ZONE_MINUTES * 60:
                anomalies.append({
                    "type": "DEAD_ZONE",
                    "severity": "INFO",
                    "detail": f"Zone {row.zone_id} has had no visits for 30+ minutes",
                    "suggested_action": f"Check display in {row.zone_id}, consider a floor staff redirect",
                    "detected_at": last.isoformat(),
                })

        # 3. Conversion drop
        entries = (
            db.query(func.count(func.distinct(StoreEvent.visitor_id)))
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "ENTRY",
                    StoreEvent.is_staff == False).scalar() or 0
        )
        billing = (
            db.query(func.count(func.distinct(StoreEvent.visitor_id)))
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "BILLING_QUEUE_JOIN",
                    StoreEvent.is_staff == False).scalar() or 0
        )
        if entries > 10:
            rate = billing / entries
            if rate < 0.10:
                anomalies.append({
                    "type": "CONVERSION_DROP",
                    "severity": "WARN",
                    "detail": f"Conversion rate {rate:.1%} is below 10% threshold",
                    "suggested_action": "Review heatmap — check if high-dwell zones are converting",
                    "detected_at": now.isoformat(),
                })

        return {"store_id": store_id, "anomalies": anomalies}
    except Exception as exc:
        raise HTTPException(503, detail={"error": "db_unavailable", "msg": str(exc)})
