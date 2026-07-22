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
2. **Ingests unstructured documentsGood — let's tackle the README next, since it's still stale and that's the first thing anyone reading this project sees.

Here's a full rewrite reflecting what the project actually does now — four action types, dry-run safety, real limitations documented, and the debugging story baked in as a feature, not hidden.

```markdown
# Self-Optimizing Multimodal Lakehouse

An agentic data platform built on Apache Iceberg that ingests structured
and unstructured data, monitors its own query performance and file health,
and uses an LLM (Gemini) to reason about problems and **autonomously fix
them** — with every decision safety-gated behind a dry-run preview.

Runs entirely free and local (Docker + MinIO standing in for cloud
object storage), with a FastAPI backend and a React dashboard.

## What it does

1. **Ingests real structured data** — 805K+ transaction rows (UCI Online
   Retail II dataset) into an Apache Iceberg table
2. **Ingests unstructured documents** (receipts) alongside it in the same
   lakehouse, with local semantic embeddings for natural-language search
3. **Logs real query performance** — files scanned, rows returned, latency,
   using actual partition-aware Iceberg scans (not simulated numbers)
4. **Analyzes both query logs and real file/partition metadata** — an LLM
   agent reasons over live table statistics (file counts, partition
   breakdown, per-column cardinality), not just logs in isolation
5. **Proposes a fix and explains its reasoning** in plain language, choosing
   from four action types (see below)
6. **Previews before touching anything** — dry-run is the default; nothing
   is applied without an explicit `--execute` flag
7. **Executes the fix for real** when approved, and logs exactly what
   changed and why

## Agent action types

| Action | What it does | Status |
|---|---|---|
| `REPARTITION_BY_COLUMN` | Adds a new partition field, choosing identity/month/bucket(N) based on column cardinality | Working |
| `REMOVE_PARTITION_FIELD` | Removes an over-granular partition field | Working |
| `COMPACT_FILES` | Rewrites existing files to match the current spec, merging small files | Working |
| `ADD_SORT_ORDER` | Adds a sort order so the query engine can use file-level min/max stats | Working (requires PyIceberg ≥ 0.11) |

The agent is deliberately conservative about high-cardinality columns: it
will never recommend an identity partition on a column with thousands of
distinct values (which would cause severe over-partitioning) — it picks a
bucket transform instead, or falls back to a sort order if bucketing isn't
possible for that column's data type.

## Known limitations (by design, documented rather than hidden)

- **`customer_id` is stored as a `double`**, not an integer, due to missing
  values during CSV ingestion (pandas upcasts int columns with NaNs to
  float). Iceberg's bucket transform doesn't support `double` source
  columns, so the agent correctly avoids `REPARTITION_BY_COLUMN` for this
  column and uses `ADD_SORT_ORDER` instead. Fixing this properly requires
  casting `customer_id` to a nullable integer type at ingestion — noted as
  a planned improvement below.
- **Sort-order writes require PyIceberg ≥ 0.11** — versions before that
  (e.g. 0.7.1) only support reading sort orders, not writing them. This
  project was originally built and debugged against 0.7.1, then upgraded
  once this constraint was discovered.

## Why this is interesting

Most student data projects stop at "I built a pipeline." This one closes
the loop: the system observes its own behavior, reasons about it with an
LLM, and takes real action on real infrastructure — not a simulation. It
also survived a real dependency upgrade (PyIceberg 0.7.1 → 0.11.1) without
silently breaking, because every failure mode along the way was diagnosed
and either fixed or explicitly documented as a constraint, rather than
worked around with a guess.

It's also honest about a genuine tradeoff discovered along the way:
partitioning by `vendor` alone doesn't meaningfully speed up the dominant
query, because one vendor ("United Kingdom") makes up ~90% of the dataset —
partition pruning only helps when a filter excludes most partitions. That's
a real lesson in query optimization, not a hidden flaw.

## Architecture
```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│    MinIO    │────▶│  Iceberg REST    │────▶│  PyIceberg  │
│ (S3-compat  │     │    Catalog       │     │   tables    │
│  storage)   │     │   (Docker)       │     │             │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                      │
                     ┌──────────────────┐            │
                     │  Query Logger    │◀───────────┤
                     └────────┬─────────┘            │
                              │                       │
                     ┌────────▼─────────┐             │
                     │  Agent (Gemini)  │             │
                     │  analyzes logs + │             │
                     │  file stats,     │─────────────▶│  (dry-run preview,
                     │  decides, and    │              │   then --execute)
                     │  executes fixes  │              │
                     └──────────────────┘              │
                                                        │
                     ┌──────────────────┐               │
                     │  FastAPI backend │◀──────────────┘
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │  React dashboard │
                     └──────────────────┘
```

## Stack
- **Storage/table format:** Apache Iceberg (via PyIceberg 0.11.1) on MinIO
- **Query engine:** PyIceberg's native scan/read
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`) — local, free, offline
- **Agent:** Google Gemini API (free tier)
- **Backend:** FastAPI
- **Frontend:** React (Vite)

## Setup

**1. Start local infrastructure:**
```bash
docker compose up -d
docker ps   # confirm lakehouse-minio and lakehouse-catalog are running
```

**2. Python environment:**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
pip install "pyiceberg[pyiceberg-core]"   # required for repartition/compaction transforms
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
python backend/query_logger.py           # logs real query performance
python agent/analyze_query_logs.py       # LLM reasons over logs + file stats
python agent/execute_decisions.py        # DRY RUN — preview only, safe by default
python agent/execute_decisions.py --execute   # actually applies the changes
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
agent/      Agent reasoning + execution logic (analyze_query_logs.py,
            execute_decisions.py, compact_and_repartition.py)
frontend/   React dashboard
data/       Sample datasets, logs, embeddings
```

## Planned improvements
- Cast `customer_id` to a nullable integer type at ingestion, to unlock
  bucket-transform partitioning for that column
- Add unit tests for `resolve_transform()` and the decision-validation logic
- CLI flag to point the pipeline at any Iceberg table, not just the sample dataset
- Exportable optimization report (Markdown/PDF) summarizing the agent's
  findings and actions for a given run
```

**What to do:** replace your `README.md` entirely with this content.

Want a demo GIF/script next — i.e. a short scripted sequence of commands that shows the whole loop off cleanly for a recruiter watching a 60-second recording?** (receipts) alongside it in the same
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

