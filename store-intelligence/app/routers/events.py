"""POST /events/ingest — Idempotent batch ingest."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database import get_db
from models import StoreEvent
from schemas import IngestRequest, IngestResponse, StoreEventIn

router = APIRouter(prefix="/events", tags=["events"])

def _to_row(e: StoreEventIn) -> dict:
    return {
        "event_id": e.event_id, "store_id": e.store_id, "camera_id": e.camera_id,
        "visitor_id": e.visitor_id, "event_type": e.event_type.value,
        "timestamp": e.timestamp, "zone_id": e.zone_id, "dwell_ms": e.dwell_ms,
        "is_staff": e.is_staff, "confidence": e.confidence,
        "queue_depth": e.metadata.queue_depth,
        "sku_zone": e.metadata.sku_zone, "session_seq": e.metadata.session_seq,
    }

@router.post("/ingest", response_model=IngestResponse)
def ingest_events(body: IngestRequest, db: Session = Depends(get_db)):
    accepted, rejected, errors = 0, 0, []
    for ev in body.events:
        try:
            stmt = (
                pg_insert(StoreEvent).values(**_to_row(ev))
                .on_conflict_do_nothing(index_elements=["event_id"])
            )
            db.execute(stmt)
            accepted += 1
        except Exception as exc:
            rejected += 1
            errors.append({"event_id": ev.event_id, "error": str(exc)})
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, detail={"error": "db_unavailable", "msg": str(exc)})
    return IngestResponse(accepted=accepted, rejected=rejected, errors=errors)
