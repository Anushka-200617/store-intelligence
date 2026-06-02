"""GET /stores/{store_id}/heatmap — Zone visit frequency + avg dwell, normalised 0-100."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import StoreEvent

router = APIRouter(prefix="/stores", tags=["heatmap"])

@router.get("/{store_id}/heatmap")
def get_heatmap(store_id: str, db: Session = Depends(get_db)):
    try:
        rows = (
            db.query(
                StoreEvent.zone_id,
                func.count(func.distinct(StoreEvent.visitor_id)).label("visit_count"),
                func.avg(StoreEvent.dwell_ms).label("avg_dwell_ms"),
            )
            .filter(StoreEvent.store_id == store_id,
                    StoreEvent.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]),
                    StoreEvent.is_staff == False, StoreEvent.zone_id != None)
            .group_by(StoreEvent.zone_id).all()
        )
        if not rows:
            return {"store_id": store_id, "zones": [], "data_confidence": "low"}

        max_visits = max(r.visit_count for r in rows) or 1
        max_dwell  = max(r.avg_dwell_ms or 0 for r in rows) or 1
        total_sessions = (
            db.query(func.count(func.distinct(StoreEvent.visitor_id)))
            .filter(StoreEvent.store_id == store_id, StoreEvent.event_type == "ENTRY",
                    StoreEvent.is_staff == False).scalar() or 0
        )
        zones = [{
            "zone_id": r.zone_id,
            "visit_count": r.visit_count,
            "avg_dwell_ms": round(r.avg_dwell_ms or 0),
            "visit_intensity": round(r.visit_count / max_visits * 100),
            "dwell_intensity": round((r.avg_dwell_ms or 0) / max_dwell * 100),
        } for r in rows]

        return {
            "store_id": store_id,
            "zones": sorted(zones, key=lambda z: z["visit_intensity"], reverse=True),
            "data_confidence": "low" if total_sessions < 20 else "high",
        }
    except Exception as exc:
        raise HTTPException(503, detail={"error": "db_unavailable", "msg": str(exc)})
