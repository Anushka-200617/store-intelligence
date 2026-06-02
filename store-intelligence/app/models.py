"""
SQLAlchemy ORM models (database tables).
Pydantic request/response schemas live in schemas.py.
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, UniqueConstraint,
)
from database import Base


class StoreEvent(Base):
    """One row per emitted event from the detection pipeline."""
    __tablename__ = "store_events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    event_id    = Column(String(36), nullable=False, unique=True)   # UUID-v4
    store_id    = Column(String(50), nullable=False, index=True)
    camera_id   = Column(String(50), nullable=False)
    visitor_id  = Column(String(50), nullable=False, index=True)
    event_type  = Column(String(30), nullable=False)
    timestamp   = Column(DateTime(timezone=True), nullable=False, index=True)
    zone_id     = Column(String(50), nullable=True)
    dwell_ms    = Column(Integer, default=0)
    is_staff    = Column(Boolean, default=False)
    confidence  = Column(Float, nullable=False)
    # metadata fields (flattened for easy querying)
    queue_depth = Column(Integer, nullable=True)
    sku_zone    = Column(String(100), nullable=True)
    session_seq = Column(Integer, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_id"),
    )
