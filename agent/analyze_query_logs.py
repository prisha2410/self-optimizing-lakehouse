"""
Reads the query log and reasons about pipeline health using Gemini.
Detects issues like "unpartitioned table causing slow high-cardinality
queries", "small-file sprawl", "over-partitioning", and "spec not
reflected in physical file layout", then proposes a concrete fix.
"""
import json
import os
from collections import defaultdict

import google.generativeai as genai
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog

load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

TABLE_NAME = "sales_db.sales"

# --- Load query stats ---
logs = []
with open("data/logs/query_log.jsonl") as f:
    for line in f:
        logs.append(json.loads(line))

logs_summary = json.dumps(logs, indent=2)

# --- Load real file/partition stats from the table itself ---
def get_file_stats(table_name):
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
    table = catalog.load_table(table_name)

    files_df = table.inspect.files().to_pandas()

    total_files = len(files_df)
    avg_file_size_mb = (files_df["file_size_in_bytes"].mean() / (1024 * 1024)) if total_files else 0
    small_file_count = int((files_df["file_size_in_bytes"] < 10 * 1024 * 1024).sum())

    partition_stats = defaultdict(lambda: {"file_count": 0, "total_size": 0})
    plan_files = list(table.scan().plan_files())

    for f in plan_files:
        key = str(f.file.partition)
        partition_stats[key]["file_count"] += 1
        partition_stats[key]["total_size"] += f.file.file_size_in_bytes

    partition_summary = [
        {
            "partition": k,
            "file_count": v["file_count"],
            "avg_file_size_mb": round(v["total_size"] / v["file_count"] / (1024 * 1024), 2),
        }
        for k, v in partition_stats.items()
    ]

    df_sample = table.scan().to_pandas()
    cardinality = {
        col: int(df_sample[col].nunique())
        for col in df_sample.columns
        if col in ("vendor", "order_date", "customer_id")
    }

    return {
        "total_files": total_files,
        "avg_file_size_mb": round(avg_file_size_mb, 2),
        "small_file_count": small_file_count,
        "partition_count": len(partition_stats),
        "partition_breakdown": partition_summary,
        "current_spec": str(table.spec()),
        "column_cardinality": cardinality,
    }

file_stats = get_file_stats(TABLE_NAME)
file_stats_summary = json.dumps(file_stats, indent=2)

# --- Known limitations the agent must respect (avoids recommending fixes that will fail) ---
KNOWN_LIMITATIONS = """
Known limitation: customer_id is stored as a double (not an integer) due to
missing values during CSV ingestion, and Iceberg's bucket transform does not
support double columns. Do not recommend REPARTITION_BY_COLUMN for customer_id
until this is fixed at the ingestion layer. If customer_id scan performance is
an issue, recommend ADD_SORT_ORDER on customer_id instead — this is a fully
supported, valid fix (not just a workaround), since sort order lets the query
engine use file-level min/max statistics to skip files even without a
partition on that column.
"""

prompt = f"""You are a data engineering agent monitoring an Apache Iceberg table's health.

Table: `{TABLE_NAME}` (805,620 rows)
Current partition spec: {file_stats['current_spec']}

--- Query execution logs ---
{logs_summary}

--- Actual file/partition layout on disk ---
{file_stats_summary}

--- Known limitations ---
{KNOWN_LIMITATIONS}

Analyze BOTH the query logs and the file layout. Identify ANY performance
inefficiency, including but not limited to:
- Unpartitioned or wrongly-partitioned columns causing slow high-cardinality queries
- Small-file sprawl (many files under 10MB in one or more partitions)
- Over-partitioning (partition_count is high relative to total_files)
- A partition spec that is defined but not reflected in the actual file layout
  (e.g. partition_count is 0 or low despite fields existing in current_spec) —
  this means existing data was never rewritten to match the spec

Action rules — follow these exactly:
- Use REPARTITION_BY_COLUMN ONLY when proposing a NEW partition field on a column
  that does NOT already appear in current_spec. target_column must be a real
  column name in this case.
- When recommending REPARTITION_BY_COLUMN, you MUST also choose a suggested_transform:
    - "identity" — only for LOW-cardinality columns (roughly under 50 distinct values,
      check column_cardinality). Creates one partition per distinct value.
    - "month" — for date/timestamp columns, buckets by calendar month.
    - "bucket:N" — for HIGH-cardinality columns (e.g. customer_id, or any column with
      hundreds or thousands of distinct values per column_cardinality). Replace N with
      a reasonable bucket count — typically between 8 and 32 depending on scale.
      NEVER use "identity" for a high-cardinality column; it causes one partition per
      value and severe over-partitioning.
- Respect the "Known limitations" section above — never recommend an action that
  is documented there as unsupported. Use the documented interim fix instead.
- If current_spec ALREADY has a field for the relevant column, but the data isn't
  physically organized into partitions (e.g. partition_count is 0), use
  COMPACT_FILES instead — this rewrites existing files to match the existing spec.
  Do NOT use REPARTITION_BY_COLUMN for this case, and target_column may be null here.
- target_column must never be null when recommended_action is REPARTITION_BY_COLUMN,
  REMOVE_PARTITION_FIELD, or ADD_SORT_ORDER.
- suggested_transform should be null for any action other than REPARTITION_BY_COLUMN.
- Do NOT recommend NO_ACTION_NEEDED for a genuine performance problem just because
  the ideal fix (e.g. partitioning) is blocked — check whether a valid alternative
  fix (e.g. ADD_SORT_ORDER) is available and recommend that instead.

For each issue found, respond in this exact JSON format (a list, even if only one issue,
empty list if genuinely no issues):

[
  {{
    "issue": "short description of the problem",
    "evidence": "which specific numbers from the logs or file stats support this",
    "recommended_action": "one of: REPARTITION_BY_COLUMN, REMOVE_PARTITION_FIELD, ADD_SORT_ORDER, COMPACT_FILES, NO_ACTION_NEEDED",
    "target_column": "column name if applicable, else null",
    "suggested_transform": "identity, month, or bucket:N — only if recommended_action is REPARTITION_BY_COLUMN, else null",
    "reasoning": "why this fix addresses the issue"
  }}
]

Respond with ONLY the JSON array, no other text."""

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(prompt)

# --- Clean and parse the response ---
raw_text = response.text.strip()
raw_text = raw_text.replace("```json", "").replace("```", "").strip()

decisions = json.loads(raw_text)

print("Agent analysis complete:\n")
for d in decisions:
    print(f"Issue: {d['issue']}")
    print(f"Evidence: {d['evidence']}")
    print(f"Recommended action: {d['recommended_action']} (target: {d['target_column']}, transform: {d.get('suggested_transform')})")
    print(f"Reasoning: {d['reasoning']}")
    print("-" * 60)

if not decisions:
    print("No issues detected — table is healthy.")

# --- Save the agent's decisions for the next step (execution) ---
os.makedirs("data/logs", exist_ok=True)
with open("data/logs/agent_decisions.json", "w") as f:
    json.dump(decisions, f, indent=2)

print(f"\nSaved {len(decisions)} decision(s) to data/logs/agent_decisions.json")