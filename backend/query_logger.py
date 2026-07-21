"""
Runs representative queries against the sales table and logs performance
stats (files scanned, rows returned, time taken) for the agent to analyze.
"""
import json
import time
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import EqualTo, And, GreaterThanOrEqual, LessThan

catalog = load_catalog(
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

table = catalog.load_table("sales_db.sales")

# --- Representative queries a real user/dashboard might run ---
queries = [
    {"name": "filter_by_vendor", "filter": EqualTo("vendor", "United Kingdom")},
    {"name": "filter_by_date_range", "filter": And(
        GreaterThanOrEqual("order_date", "2010-01-01T00:00:00"),
        LessThan("order_date", "2010-02-01T00:00:00"),
    )},
    {"name": "filter_by_customer", "filter": EqualTo("customer_id", 17850.0)},
]

log_entries = []

for q in queries:
    scan = table.scan(row_filter=q["filter"])

    start = time.time()
    plan_files = list(scan.plan_files())
    result = scan.to_pandas()
    elapsed = time.time() - start

    entry = {
        "query_name": q["name"],
        "filter_expr": str(q["filter"]),
        "files_scanned": len(plan_files),
        "rows_returned": len(result),
        "elapsed_seconds": round(elapsed, 3),
    }
    log_entries.append(entry)
    print(f"{q['name']}: scanned {entry['files_scanned']} files, "
          f"returned {entry['rows_returned']} rows, took {entry['elapsed_seconds']}s")

# --- Save the log for the agent to analyze ---
import os
os.makedirs("data/logs", exist_ok=True)
with open("data/logs/query_log.jsonl", "a") as f:
    for entry in log_entries:
        f.write(json.dumps(entry) + "\n")

print(f"\nLogged {len(log_entries)} query stats to data/logs/query_log.jsonl")