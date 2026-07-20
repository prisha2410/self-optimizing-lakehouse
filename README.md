# Self-Optimizing Multimodal Lakehouse

An agentic data platform that ingests structured + unstructured data into an
Apache Iceberg lakehouse, and uses an AI agent to monitor query patterns and
**autonomously tune itself** — triggering compaction, repartitioning, and
flagging anomalies — with every decision logged and explained.

Runs entirely free/local via Docker (MinIO stands in for Azure Blob Storage
during development). Can be pointed at real Azure for a live cloud demo.

## Stack
- **Storage/table format:** Apache Iceberg on MinIO (local) / Azure Blob (cloud demo)
- **Query engine:** DuckDB
- **Embeddings:** sentence-transformers (local, free) for semantic search over documents
- **Agent:** Gemini free tier — reasons about pipeline health and takes action
- **Backend:** FastAPI
- **Frontend:** React

## Status
🚧 Day 1 — environment scaffolding

## Setup
```bash
# 1. Start local infra (MinIO + Iceberg REST catalog)
docker compose up -d

# 2. Create a Python virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Check MinIO console (login: admin / password123)
open http://localhost:9001
```

## Project structure
```
backend/    FastAPI app — ingestion, query, and agent-status endpoints
agent/      Agent logic — monitors stats, decides + executes tuning actions
frontend/   React dashboard
data/       Sample datasets for local testing
docs/       Architecture notes, diagrams
```

## Roadmap
- [x] Day 1 — Docker environment, Iceberg tables
- [ ] Day 2 — Multimodal ingestion + embeddings
- [ ] Day 3 — Query stats logging + agent decision logic
- [ ] Day 4 — Self-tuning actions + FastAPI backend
- [ ] Day 5 — React dashboard + NL query
- [ ] Day 6 — Azure cloud demo
- [ ] Day 7 — Docs, demo video, polish
