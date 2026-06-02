#!/usr/bin/env bash
# ================================================================
# Store Intelligence — Detection Pipeline Runner
# Processes all CCTV clips and feeds events into the API
#
# Usage:
#   bash run.sh                          # uses default clips path
#   bash run.sh /custom/path/to/clips    # custom clips directory
# ================================================================

set -e  # stop on any error

# ── Paths ────────────────────────────────────────────────────────
CLIPS_DIR="${1:-../data/clips}"
EVENTS_DIR="../data/events"
LAYOUT="../data/store_layout.json"
STORE_ID="ST1008"
OUTPUT="$EVENTS_DIR/${STORE_ID}.jsonl"

# ── Clip start time (IST 20:09 = UTC 14:39) ──────────────────────
CLIP_START="2026-04-10T14:39:00Z"

# ── Setup ────────────────────────────────────────────────────────
mkdir -p "$EVENTS_DIR"

# Clear previous events so we don't double-count on re-runs
if [ -f "$OUTPUT" ]; then
    echo "⚠  Removing old events file: $OUTPUT"
    rm "$OUTPUT"
fi

echo "============================================"
echo " Store Intelligence — Detection Pipeline"
echo " Store    : $STORE_ID"
echo " Clips    : $CLIPS_DIR"
echo " Output   : $OUTPUT"
echo " Start    : $CLIP_START"
echo "============================================"
echo ""

# ── CAM 3 — Entry / Exit threshold (MOST IMPORTANT) ──────────────
echo ">>> [1/4] CAM 3 — Entry/Exit camera"
python detect.py \
  --clip          "$CLIPS_DIR/CAM 3.mp4" \
  --store-id      "$STORE_ID" \
  --camera-id     "CAM_ENTRY_01" \
  --clip-start    "$CLIP_START" \
  --output        "$OUTPUT" \
  --store-layout  "$LAYOUT"
echo "    Done. Events so far: $(wc -l < "$OUTPUT")"
echo ""

# ── CAM 1 — Main floor: Skincare zone ────────────────────────────
echo ">>> [2/4] CAM 1 — Skincare floor camera"
python detect.py \
  --clip          "$CLIPS_DIR/CAM 1.mp4" \
  --store-id      "$STORE_ID" \
  --camera-id     "CAM_FLOOR_SKINCARE" \
  --clip-start    "$CLIP_START" \
  --output        "$OUTPUT" \
  --store-layout  "$LAYOUT"
echo "    Done. Events so far: $(wc -l < "$OUTPUT")"
echo ""

# ── CAM 2 — Main floor: Makeup zone ──────────────────────────────
echo ">>> [3/4] CAM 2 — Makeup floor camera"
python detect.py \
  --clip          "$CLIPS_DIR/CAM 2.mp4" \
  --store-id      "$STORE_ID" \
  --camera-id     "CAM_FLOOR_MAKEUP" \
  --clip-start    "$CLIP_START" \
  --output        "$OUTPUT" \
  --store-layout  "$LAYOUT"
echo "    Done. Events so far: $(wc -l < "$OUTPUT")"
echo ""

# ── CAM 5 — Billing counter ───────────────────────────────────────
echo ">>> [4/4] CAM 5 — Billing counter camera"
python detect.py \
  --clip          "$CLIPS_DIR/CAM 5.mp4" \
  --store-id      "$STORE_ID" \
  --camera-id     "CAM_BILLING_01" \
  --clip-start    "$CLIP_START" \
  --output        "$OUTPUT" \
  --store-layout  "$LAYOUT"
echo "    Done. Events so far: $(wc -l < "$OUTPUT")"
echo ""

# ── CAM 4 skipped (stockroom — staff only, no customer data) ─────
echo ">>> CAM 4 skipped (stockroom/back office — not relevant)"
echo ""

# ── Ingest into API ───────────────────────────────────────────────
echo "============================================"
echo " Ingesting $(wc -l < "$OUTPUT") events into API..."
echo "============================================"
python ingest_events.py \
  --events  "$OUTPUT" \
  --api-url "http://localhost:8000"

echo ""
echo "============================================"
echo "✅ Pipeline complete!"
echo "   Events file : $OUTPUT"
echo "   Check API   : curl http://localhost:8000/stores/ST1008/metrics"
echo "   Dashboard   : curl http://localhost:8000/stores/ST1008/funnel"
echo "============================================"