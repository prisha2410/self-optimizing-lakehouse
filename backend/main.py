"""
FastAPI backend wrapping the lakehouse pipeline: ingestion status,
query execution, and agent trigger/status endpoints.
"""
from sentence_transformers import SentenceTransformer  # import order safety, used by /search endpoint
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import subprocess
import pandas as pd
import numpy as np
from pyiceberg.catalog import load_catalog

app = FastAPI(title="Self-Optimizing Lakehouse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # fine for local dev; tighten if you ever deploy publicly
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_catalog():
    return load_catalog(
        "lakehouse",
        **{
            "uri": "http://localhost:8181",
            "s3.endpoint": "http://localhost:9000",
            "s3.access-key-id": "admin",
            "s3.secret-access-key": "password123",
            "s3.path-style-access": "true",
            "downcast-ns-timestamp-to-us-on-write": "true",
        },
    )

_embed_model = None
def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


@app.get("/")
def root():
    return {"status": "ok", "service": "self-optimizing-lakehouse"}


@app.get("/tables")
def list_tables():
    """List tables in the lakehouse with basic stats."""
    catalog = get_catalog()
    result = []
    for namespace in catalog.list_namespaces():
        for table_name in catalog.list_tables(namespace[0]):
            full_name = f"{table_name[0]}.{table_name[1]}"
            table = catalog.load_table(full_name)
            files = list(table.scan().plan_files())
            result.append({
                "name": full_name,
                "partition_spec": str(table.spec()),
                "file_count": len(files),
            })
    return {"tables": result}


@app.get("/tables/{namespace}/{table_name}/sample")
def sample_table(namespace: str, table_name: str, limit: int = 10):
    """Return a small sample of rows from a table."""
    catalog = get_catalog()
    try:
        table = catalog.load_table(f"{namespace}.{table_name}")
    except Exception:
        raise HTTPException(status_code=404, detail="Table not found")

    df = table.scan(limit=limit).to_pandas()
    df = df.drop(columns=["embedding"], errors="ignore")  # embeddings aren't useful to display raw
    return {"rows": json.loads(df.to_json(orient="records"))}


@app.get("/query-log")
def get_query_log():
    """Return logged query performance stats."""
    path = "data/logs/query_log.jsonl"
    if not os.path.exists(path):
        return {"entries": []}
    entries = []
    with open(path) as f:
        for line in f:
            entries.append(json.loads(line))
    return {"entries": entries}


@app.get("/agent/decisions")
def get_agent_decisions():
    """Return the agent's most recent analysis/decisions."""
    path = "data/logs/agent_decisions.json"
    if not os.path.exists(path):
        return {"decisions": []}
    with open(path) as f:
        return {"decisions": json.load(f)}


@app.get("/agent/executed-actions")
def get_executed_actions():
    """Return what the agent actually executed."""
    path = "data/logs/executed_actions.json"
    if not os.path.exists(path):
        return {"executed": []}
    with open(path) as f:
        return {"executed": json.load(f)}


@app.post("/agent/run-analysis")
def run_agent_analysis():
    """Trigger the agent to re-analyze current query logs."""
    result = subprocess.run(
        ["python", "agent/analyze_query_logs.py"],
        capture_output=True, text=True, cwd=os.getcwd(),
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr[-2000:])
    with open("data/logs/agent_decisions.json") as f:
        decisions = json.load(f)
    return {"status": "completed", "decisions": decisions, "log": result.stdout[-2000:]}


@app.get("/search")
def semantic_search(q: str, top_k: int = 5):
    """Semantic search over receipt documents using local embeddings."""
    path = "data/sample/receipts_embeddings.parquet"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No embeddings found")

    df = pd.read_parquet(path)
    model = get_embed_model()
    query_embedding = model.encode(q)
    embeddings_matrix = np.stack(df["embedding"].values)

    similarities = embeddings_matrix @ query_embedding / (
        np.linalg.norm(embeddings_matrix, axis=1) * np.linalg.norm(query_embedding)
    )
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        row = df.iloc[idx]
        results.append({
            "doc_id": row["doc_id"],
            "vendor": row["vendor"],
            "category": row["category"],
            "total": float(row["total"]),
            "similarity": float(similarities[idx]),
        })
    return {"query": q, "results": results}