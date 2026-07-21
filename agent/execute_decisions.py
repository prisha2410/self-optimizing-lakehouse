"""
Reads the agent's saved decisions and actually executes them —
this is what makes the pipeline "self-optimizing" rather than
just "self-reporting".
"""
import json
from pyiceberg.catalog import load_catalog
from pyiceberg.transforms import IdentityTransform, MonthTransform

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

with open("data/logs/agent_decisions.json") as f:
    decisions = json.load(f)

print(f"Current partition spec: {table.spec()}\n")

executed_log = []

for decision in decisions:
    action = decision["recommended_action"]
    column = decision["target_column"]

    if action != "REPARTITION_BY_COLUMN":
        print(f"Skipping '{decision['issue']}' — action '{action}' not yet implemented")
        continue

    # Choose transform: dates get bucketed by month, everything else is identity
    if column == "order_date":
        transform = MonthTransform()
        field_name = "order_date_month"
    else:
        transform = IdentityTransform()
        field_name = f"{column}_partition"

    # Check it's not already partitioned by this column
    existing_fields = [f.name for f in table.spec().fields]
    if field_name in existing_fields:
        print(f"Already partitioned by {column} — skipping")
        continue

    print(f"Executing: repartitioning by '{column}' using {transform.__class__.__name__}...")
    with table.update_spec() as update:
        update.add_field(column, transform, field_name)

    executed_log.append({
        "column": column,
        "transform": transform.__class__.__name__,
        "issue_addressed": decision["issue"],
    })
    print(f"  -> Done. New partition field: {field_name}")

print(f"\nUpdated partition spec: {table.spec()}\n")

with open("data/logs/executed_actions.json", "w") as f:
    json.dump(executed_log, f, indent=2)

print(f"Executed {len(executed_log)} action(s). Logged to data/logs/executed_actions.json")