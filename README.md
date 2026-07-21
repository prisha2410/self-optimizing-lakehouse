# Self-Optimizing Multimodal Lakehouse

An agentic data platform built on Apache Iceberg that ingests structured
and unstructured data, and uses an LLM agent to monitor query performance
and **autonomously repartition tables** when it detects inefficiency —
with every decision logged, reasoned, and executed end-to-end.

Runs entirely free and local (Docker + MinIO standing in for cloud
object storage), with a FastAPI backend and a React dashboard.

## What it does

1. **Ingests real structured data** — 805K+ transaction rows (UCI Online
   Retail II dataset) into an Apache Iceberg table
2. **Ingests unstructured documents** (receipts) alongside it in the same
   lakehouse, with local semantic embeddings for natural-language search
3. **Logs query performance** — files scanned, rows returned, latency
4. **An LLM agent analyzes these logs**, identifies inefficiencies (e.g.
   too many small files, poor partition pruning), and decides on a
   corrective action
5. **Executes the fix automatically** — repartitioning or compacting
   tables — and logs exactly what it changed and why

## Setup

**1. Clone the repo and enter it:**
```bash
git clone <your-repo-url>
cd <your-repo-name>
```

**2. Python environment:**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

**3. Environment variables** — create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```
(Get a free key at https://aistudio.google.com/apikey)

**4. Build the lakehouse:**
```bash
python data/sample/download_public_dataset.py
python backend/create_first_table.py
python data/sample/generate_receipts.py
python backend/generate_embeddings.py
python backend/create_receipts_table.py
```

**5. Run the agent loop:**
```bash
python backend/query_logger.py
python agent/analyze_query_logs.py
python agent/execute_decisions.py
python agent/compact_and_repartition.py
```

**6. Start the backend:**
```bash
uvicorn backend.main:app --reload --port 8000
```

**7. Start the frontend** (in a separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`.

## API endpoints
- `GET /tables` — list lakehouse tables with partition specs and file counts
- `GET /query-log` — query performance history
- `GET /agent/decisions` — the agent's latest analysis
- `GET /agent/executed-actions` — what the agent actually changed
- `POST /agent/run-analysis` — trigger a fresh agent analysis
- `GET /search?q=...` — semantic search over unstructured documents

## Project structure
```
backend/    FastAPI app, Iceberg table creation, query logging
agent/      Agent reasoning + execution logic
frontend/   React dashboard
data/       Sample datasets, logs, embeddings
```
```
