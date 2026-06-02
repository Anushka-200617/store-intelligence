"""GET /stores/{store_id}/metrics — Real-time KPIs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import StoreEvent

router = APIRouter(prefix="/stores", tags=["metrics"])

@router.get("/{store_id}/metrics")
def get_metrics(store_id: str, db: Session = Depends(get_db)):
    try:
        def count_unique(event_type: str) -> int:
            return (
                db.query(func.count(func.distinct(StoreEvent.visitor_id)))
                .filter(StoreEvent.store_id == store_id,
                        StoreEvent.event_type == event_type,
                        StoreEvent.is_staff == False)
                .scalar() or 0
            )

        unique_visitors  = count_unique("ENTRY")
        billing_sessions = count_unique("BILLING_QUEUE_JOIN")
        abandoned        = count_unique("BILLING_QUEUE_ABANDON")

        conversion_rate  = round(billing_sessions / unique_visitors, 4) if unique_visitors else 0.0
        abandonment_rate = round(abandoned / billing_sessions, 4) if billing_sessions else 0.0

        zone_dwell = (
            db.query(StoreEvent.zone_id, func.avg(StoreEvent.dwell_ms).label("avg_dwell"))
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "ZONE_DWELL",
                    StoreEvent.is_staff == False, StoreEvent.zone_id != None)
            .group_by(StoreEvent.zone_id).all()
        )
        latest_queue = (
            db.query(StoreEvent.queue_depth)
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "BILLING_QUEUE_JOIN")
            .order_by(StoreEvent.timestamp.desc()).first()
        )
        return {
            "store_id": store_id,
            "unique_visitors": unique_visitors,
            "conversion_rate": conversion_rate,
            "billing_sessions": billing_sessions,
            "abandonment_rate": abandonment_rate,
            "queue_depth": latest_queue[0] if latest_queue else 0,
            "avg_dwell_by_zone": {r.zone_id: round(r.avg_dwell) for r in zone_dwell},
        }
    except Exception as exc:
        raise HTTPException(503, detail={"error": "db_unavailable", "msg": str(exc)})
