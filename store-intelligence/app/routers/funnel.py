"""GET /stores/{store_id}/funnel — Conversion funnel (session-based, no double-count)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import StoreEvent

router = APIRouter(prefix="/stores", tags=["funnel"])

@router.get("/{store_id}/funnel")
def get_funnel(store_id: str, db: Session = Depends(get_db)):
    try:
        def count_unique(event_type: str) -> int:
            return (
                db.query(func.count(func.distinct(StoreEvent.visitor_id)))
                .filter(StoreEvent.store_id == store_id,
                        StoreEvent.event_type == event_type,
                        StoreEvent.is_staff == False)
                .scalar() or 0
            )

        entries        = count_unique("ENTRY")
        zone_visitors  = count_unique("ZONE_ENTER")
        billing_joined = count_unique("BILLING_QUEUE_JOIN")
        abandoned      = count_unique("BILLING_QUEUE_ABANDON")
        purchases      = max(0, billing_joined - abandoned)

        def drop_off(cur: int, prev: int) -> float:
            return round((prev - cur) / prev * 100, 2) if prev else 0.0

        return {
            "store_id": store_id,
            "funnel": [
                {"stage": "entry",         "visitors": entries,        "drop_off_pct": 0.0},
                {"stage": "zone_visit",    "visitors": zone_visitors,  "drop_off_pct": drop_off(zone_visitors,  entries)},
                {"stage": "billing_queue", "visitors": billing_joined, "drop_off_pct": drop_off(billing_joined, zone_visitors)},
                {"stage": "purchase",      "visitors": purchases,      "drop_off_pct": drop_off(purchases,      billing_joined)},
            ],
        }
    except Exception as exc:
        raise HTTPException(503, detail={"error": "db_unavailable", "msg": str(exc)})
