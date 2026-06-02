"""
Pydantic v2 schemas for request validation and response serialisation.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class EventType(str, Enum):
    ENTRY                 = "ENTRY"
    EXIT                  = "EXIT"
    ZONE_ENTER            = "ZONE_ENTER"
    ZONE_EXIT             = "ZONE_EXIT"
    ZONE_DWELL            = "ZONE_DWELL"
    BILLING_QUEUE_JOIN    = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY               = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone:    Optional[str] = None
    session_seq: Optional[int] = None


class StoreEventIn(BaseModel):
    """Schema the detection pipeline emits (and we ingest)."""
    event_id:   str                   = Field(..., description="UUID-v4")
    store_id:   str
    camera_id:  str
    visitor_id: str
    event_type: EventType
    timestamp:  datetime
    zone_id:    Optional[str]         = None
    dwell_ms:   int                   = 0
    is_staff:   bool                  = False
    confidence: float                 = Field(..., ge=0.0, le=1.0)
    metadata:   EventMetadata         = Field(default_factory=EventMetadata)

    @field_validator("event_id")
    @classmethod
    def must_be_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("event_id must be a valid UUID-v4")
        return v


class IngestRequest(BaseModel):
    events: list[StoreEventIn] = Field(..., max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    errors:   list[dict[str, Any]] = []
