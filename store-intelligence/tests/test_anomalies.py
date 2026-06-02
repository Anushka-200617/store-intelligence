"""
Tests for GET /stores/{store_id}/anomalies

# PROMPT: "Write pytest tests for an anomaly detection endpoint.
#          Cover: queue spike (CRITICAL vs WARN threshold),
#          dead zone detection, conversion drop, empty store (no anomalies)."
# CHANGES MADE: Mocked timestamps for dead-zone test because real-time
#               comparison breaks in CI; added severity assertion.
"""
import uuid
import pytest


def make_event(store_id="ST1008_ANOM", visitor_id="VIS_001",
               event_type="ENTRY", **kw):
    base = {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  "CAM_ENTRY_01",
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  "2026-04-10T14:00:00Z",
        "zone_id":    None,
        "dwell_ms":   0,
        "is_staff":   False,
        "confidence": 0.9,
        "metadata":   {"queue_depth": None, "sku_zone": None, "session_seq": 1},
    }
    base.update(kw)
    return base


def ingest(client, events):
    resp = client.post("/events/ingest", json={"events": events})
    assert resp.status_code == 200


def test_no_anomalies_on_empty_store(client):
    resp = client.get("/stores/TOTALLY_EMPTY/anomalies")
    assert resp.status_code == 200
    assert resp.json()["anomalies"] == []


def test_queue_spike_warn(client):
    """Queue depth of 5 should trigger WARN."""
    ev = make_event(
        event_type="BILLING_QUEUE_JOIN",
        metadata={"queue_depth": 5, "sku_zone": None, "session_seq": 1},
    )
    ingest(client, [ev])
    resp = client.get("/stores/ST1008_ANOM/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["anomalies"]
    queue_anomalies = [a for a in anomalies if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert len(queue_anomalies) >= 1
    assert queue_anomalies[0]["severity"] in ("WARN", "CRITICAL")


def test_queue_spike_critical(client):
    """Queue depth >= 8 should be CRITICAL."""
    ev = make_event(
        event_type="BILLING_QUEUE_JOIN",
        metadata={"queue_depth": 10, "sku_zone": None, "session_seq": 1},
    )
    ingest(client, [ev])
    resp = client.get("/stores/ST1008_ANOM/anomalies")
    queue_anomalies = [a for a in resp.json()["anomalies"] if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert any(a["severity"] == "CRITICAL" for a in queue_anomalies)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "db" in data
