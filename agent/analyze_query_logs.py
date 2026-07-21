"""
Reads the query log and reasons about pipeline health using Gemini.
Detects issues like "unpartitioned table causing slow high-cardinality
queries" and proposes a concrete fix.
"""
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# --- Load query stats ---
logs = []
with open("data/logs/query_log.jsonl") as f:
    for line in f:
        logs.append(json.loads(line))

logs_summary = json.dumps(logs, indent=2)

prompt = f"""You are a data engineering agent monitoring an Apache Iceberg table's query performance.

Here are recent query execution logs from the table `sales_db.sales` (805,620 rows, currently stored as a single unpartitioned file):

{logs_summary}

Analyze these logs and identify ANY performance inefficiency. For each issue found, respond in this exact JSON format (a list, even if only one issue):

[
  {{
    "issue": "short description of the problem",
    "evidence": "which specific numbers from the logs support this",
    "recommended_action": "one of: REPARTITION_BY_COLUMN, ADD_SORT_ORDER, COMPACT_FILES, NO_ACTION_NEEDED",
    "target_column": "column name if applicable, else null",
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
    print(f"Recommended action: {d['recommended_action']} (target: {d['target_column']})")
    print(f"Reasoning: {d['reasoning']}")
    print("-" * 60)

# --- Save the agent's decisions for the next step (execution) ---
os.makedirs("data/logs", exist_ok=True)
with open("data/logs/agent_decisions.json", "w") as f:
    json.dump(decisions, f, indent=2)

print(f"\nSaved {len(decisions)} decision(s) to data/logs/agent_decisions.json")