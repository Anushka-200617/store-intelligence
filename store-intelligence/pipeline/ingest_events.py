"""
Reads a JSONL events file and POSTs batches to the API.
Used by run.sh after detection to feed events into the intelligence API.
"""
import argparse
import json
import sys
import httpx
from pathlib import Path

API_URL = "http://localhost:8000"
BATCH_SIZE = 200

def ingest(events_path: str):
    events = []
    with open(events_path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    print(f"Loaded {len(events)} events from {events_path}")
    batches = [events[i:i+BATCH_SIZE] for i in range(0, len(events), BATCH_SIZE)]
    total_accepted = 0

    with httpx.Client(base_url=API_URL, timeout=30) as client:
        for i, batch in enumerate(batches):
            resp = client.post("/events/ingest", json={"events": batch})
            if resp.status_code == 200:
                data = resp.json()
                total_accepted += data["accepted"]
                print(f"Batch {i+1}/{len(batches)}: accepted={data['accepted']} rejected={data['rejected']}")
            else:
                print(f"Batch {i+1} failed: {resp.status_code} {resp.text}", file=sys.stderr)

    print(f"✅ Done. Total accepted: {total_accepted}/{len(events)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--api-url", default=API_URL)
    args = parser.parse_args()
    API_URL = args.api_url
    ingest(args.events)
