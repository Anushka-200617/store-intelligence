"""GET /health — Service status, last event per store, STALE_FEED warning."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from database import get_db
from models import StoreEvent

router = APIRouter(tags=["health"])

@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        return {"status": "degraded", "db": "unavailable", "warnings": ["DATABASE_UNAVAILABLE"]}

    now = datetime.now(timezone.utc)
    warnings = []
    rows = (
        db.query(StoreEvent.store_id, func.max(StoreEvent.timestamp).label("last_event"))
        .group_by(StoreEvent.store_id).all()
    )
    store_feeds = {}
    for row in rows:
        last = row.last_event
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        stale = last is None or (now - last).total_seconds() > 600
        if stale:
            warnings.append(f"STALE_FEED:{row.store_id}")
        store_feeds[row.store_id] = {"last_event": last.isoformat() if last else None, "stale": stale}

    return {"status": "ok", "db": db_status, "store_feeds": store_feeds,
            "warnings": warnings, "checked_at": now.isoformat()}
