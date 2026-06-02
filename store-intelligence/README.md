
# Store Intelligence System

A system that processes CCTV footage from retail stores to track customers and calculate conversion rates.

## Quick Start

### 1. Clone and Setup
``````bash
git clone <your-repo>
cd store-intelligence
``````

### 2. Start the API
``````bash
docker compose up --build -d
``````

The API will be available at http://localhost:8000

### 3. Verify API is Working
``````bash
curl http://localhost:8000/health
``````

## Running Detection Pipeline

The detection pipeline processes CCTV video clips and generates events.

### Setup Pipeline Environment
``````bash
cd pipeline
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
``````

### Run Detection

Process all cameras:
``````bash
bash run.sh
``````

Output events go to: data/events/STORE_BLR_002.jsonl

## Ingest Events

``````bash
python ingest_events.py --events "../data/events/STORE_BLR_002.jsonl"
``````

## API Endpoints

### Get Metrics
``````bash
curl http://localhost:8000/stores/STORE_BLR_002/metrics
``````

Example response:
``````json
{
  "store_id": "STORE_BLR_002",
  "unique_visitors": 14,
  "conversion_rate": 0.5714,
  "billing_sessions": 8,
  "abandonment_rate": 0.0
}
``````

### Get Funnel
``````bash
curl http://localhost:8000/stores/STORE_BLR_002/funnel
``````

### Get Heatmap
``````bash
curl http://localhost:8000/stores/STORE_BLR_002/heatmap
``````

### Check Health
``````bash
curl http://localhost:8000/health
``````

## Architecture

See docs/DESIGN.md for system architecture.

See docs/CHOICES.md for design decisions.

## Results

Test Store (STORE_BLR_002):
- Unique visitors: 14
- Conversion rate: 57.14%
- Billing sessions: 8
- Queue abandonment: 0%
- Events processed: 155
