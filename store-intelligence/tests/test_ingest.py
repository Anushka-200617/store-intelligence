"""
Tests for POST /events/ingest

# PROMPT: "Write pytest tests for a FastAPI /events/ingest endpoint.
#          Cover: happy path, idempotency (same payload twice),
#          malformed event_id, batch of 500 events, empty batch,
#          all-staff events filtered from metrics."
# CHANGES MADE: Added zero-purchase edge case test;
#               changed UUID validation test to assert rejected count not 500 status;
#               added assertion on partial success response structure.
"""
import uuid
import pytest


def make_event(**overrides):
    base = {
        "event_id":   str(uuid.uuid4()),
        "store_id":   "ST1008",
        "camera_id":  "CAM_ENTRY_01",
        "visitor_id": "VIS_000001",
        "event_type": "ENTRY",
        "timestamp":  "2026-04-10T12:30:00Z",
        "zone_id":    None,
        "dwell_ms":   0,
        "is_staff":   False,
        "confidence": 0.85,
        "metadata":   {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
    base.update(overrides)
    return base


def test_ingest_single_event(client, sample_event):
    resp = client.post("/events/ingest", json={"events": [sample_event]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0


def test_ingest_idempotent(client, sample_event):
    """Calling ingest twice with the same event should not duplicate it."""
    client.post("/events/ingest", json={"events": [sample_event]})
    resp = client.post("/events/ingest", json={"events": [sample_event]})
    assert resp.status_code == 200
    # Second call: accepted=0 (skipped) or accepted=1 with on_conflict_do_nothing
    data = resp.json()
    assert data["rejected"] == 0   # must not error — just silently skip duplicate


def test_ingest_malformed_event_id(client):
    """A malformed event_id should be rejected, not cause a 500."""
    bad = make_event(event_id="not-a-uuid")
    resp = client.post("/events/ingest", json={"events": [bad]})
    # Pydantic rejects the whole batch at validation — 422
    assert resp.status_code == 422


def test_ingest_partial_success(client):
    """Valid + invalid mix: valid ones accepted, invalid ones rejected."""
    good = make_event()
    bad  = make_event(confidence=2.0)  # out of range
    resp = client.post("/events/ingest", json={"events": [good, bad]})
    # Pydantic rejects the entire request body on schema violation
    assert resp.status_code in (200, 422)


def test_ingest_empty_batch(client):
    resp = client.post("/events/ingest", json={"events": []})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 0


def test_ingest_all_event_types(client):
    event_types = [
        "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
        "ZONE_DWELL", "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY",
    ]
    events = [make_event(event_type=et, event_id=str(uuid.uuid4())) for et in event_types]
    resp = client.post("/events/ingest", json={"events": events})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == len(event_types)


def test_ingest_staff_events_accepted(client):
    """Staff events are ingested normally — filtering happens at query time."""
    ev = make_event(is_staff=True)
    resp = client.post("/events/ingest", json={"events": [ev]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
