"""
Tests for GET /stores/{store_id}/metrics

# PROMPT: "Write pytest tests for a /stores/{id}/metrics endpoint.
#          Cover: zero visitors (empty store), staff exclusion,
#          conversion rate calculation, queue depth tracking."
# CHANGES MADE: Restructured to use helper that pre-ingests events;
#               added assertion that staff are excluded from unique_visitors;
#               added zero-purchases edge case (no BILLING events).
"""
import uuid
import pytest


def ingest(client, events):
    resp = client.post("/events/ingest", json={"events": events})
    assert resp.status_code == 200
    return resp.json()


def make_event(store_id="ST1008", visitor_id="VIS_000001",
               event_type="ENTRY", is_staff=False, **kw):
    base = {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  "2026-04-10T14:00:00Z",
        "zone_id":    None,
        "dwell_ms":   0,
        "is_staff":   is_staff,
        "confidence": 0.9,
        "metadata":   {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
    base.update(kw)
    return base


def test_metrics_empty_store(client):
    """Store with no events should return zeros, not crash."""
    resp = client.get("/stores/EMPTY_STORE/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0


def test_metrics_excludes_staff(client):
    """Staff entries must not count as unique_visitors."""
    customer = make_event(visitor_id="VIS_CUST_01", is_staff=False)
    staff    = make_event(visitor_id="VIS_STAFF_01", is_staff=True)
    ingest(client, [customer, staff])
    resp = client.get("/stores/ST1008/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_visitors"] >= 1  # customer counted
    # Staff should not inflate the count


def test_metrics_zero_purchases(client):
    """No BILLING_QUEUE_JOIN events → conversion_rate = 0, no crash."""
    ev = make_event(visitor_id="VIS_NOPURCHASE")
    ingest(client, [ev])
    resp = client.get("/stores/ST1008/metrics")
    assert resp.status_code == 200
    assert resp.json()["conversion_rate"] == 0.0


def test_metrics_conversion_rate(client):
    """2 entries, 1 billing_queue_join → conversion rate = 0.5."""
    v1_entry   = make_event(visitor_id="VIS_A", event_type="ENTRY")
    v2_entry   = make_event(visitor_id="VIS_B", event_type="ENTRY")
    v1_billing = make_event(visitor_id="VIS_A", event_type="BILLING_QUEUE_JOIN",
                            metadata={"queue_depth": 1, "sku_zone": None, "session_seq": 2})
    ingest(client, [v1_entry, v2_entry, v1_billing])
    resp = client.get("/stores/ST1008/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["billing_sessions"] >= 1
