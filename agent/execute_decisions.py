"""
Reads the agent's saved decisions and executes them —
this is what makes the pipeline "self-optimizing" rather than
just "self-reporting".

Defaults to DRY RUN (preview only). Pass --execute to actually apply changes.
"""
import argparse
import json
from pyiceberg.catalog import load_catalog
from pyiceberg.transforms import IdentityTransform, MonthTransform, BucketTransform
from pyiceberg.table.sorting import NullOrder

TABLE_NAME = "sales_db.sales"

COLUMN_REQUIRED_ACTIONS = {"REPARTITION_BY_COLUMN", "REMOVE_PARTITION_FIELD", "ADD_SORT_ORDER"}

def load_catalog_conn():
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

def resolve_transform(table, column, decision):
    """Turns the agent's suggested_transform string into a real PyIceberg
    transform + field name. Returns (None, None, reason) if incompatible."""
    suggestion = (decision.get("suggested_transform") or "").strip().lower()

    field = next((f for f in table.schema().fields if f.name == column), None)
    if field is None:
        return None, None, f"column '{column}' not found in schema"

    source_type = str(field.field_type).lower()

    if column == "order_date" or suggestion == "month":
        return MonthTransform(), f"{column}_month", None

    if suggestion.startswith("bucket:"):
        try:
            n = int(suggestion.split(":", 1)[1])
        except (IndexError, ValueError):
            n = 16

        if source_type in ("double", "float"):
            return None, None, (
                f"column '{column}' is stored as {source_type}, but bucket transforms "
                f"require an integer, string, or similar discrete type. This needs a "
                f"schema/ingestion fix (cast {column} to a nullable integer type at "
                f"ingestion), not a partitioning fix."
            )
        return BucketTransform(n), f"{column}_bucket_{n}", None

    if suggestion == "identity":
        return IdentityTransform(), f"{column}_partition", None

    return None, None, f"no valid suggested_transform given for '{column}'"

def handle_repartition(table, decision, dry_run, preview_log, executed_log):
    column = decision["target_column"]
    transform, field_name, skip_reason = resolve_transform(table, column, decision)

    if transform is None:
        print(f"Skipping '{decision['issue']}' — {skip_reason}")
        return

    existing_fields = [f.name for f in table.spec().fields]
    if field_name in existing_fields:
        print(f"Already partitioned by {column} — skipping")
        return

    if dry_run:
        print(f"Would repartition by '{column}' using {transform.__class__.__name__}")
        print(f"  -> New partition field would be: {field_name}")
        print(f"  -> Addresses issue: {decision['issue']}\n")
        preview_log.append({
            "action": "REPARTITION_BY_COLUMN",
            "column": column,
            "transform": transform.__class__.__name__,
            "new_field_name": field_name,
            "issue_addressed": decision["issue"],
        })
        return

    print(f"Executing: repartitioning by '{column}' using {transform.__class__.__name__}...")
    with table.update_spec() as update:
        update.add_field(column, transform, field_name)

    executed_log.append({
        "action": "REPARTITION_BY_COLUMN",
        "column": column,
        "transform": transform.__class__.__name__,
        "issue_addressed": decision["issue"],
    })
    print(f"  -> Done. New partition field: {field_name}")

def handle_remove_partition_field(table, decision, dry_run, preview_log, executed_log):
    column = decision["target_column"]
    existing_fields = [f.name for f in table.spec().fields]

    candidates = [f for f in existing_fields if f.startswith(column)]
    if not candidates:
        print(f"No partition field found for '{column}' — skipping")
        return
    field_name = candidates[0]

    if dry_run:
        print(f"Would remove over-granular partition field '{field_name}'")
        print(f"  -> Addresses issue: {decision['issue']}\n")
        preview_log.append({
            "action": "REMOVE_PARTITION_FIELD",
            "column": column,
            "field_removed": field_name,
            "issue_addressed": decision["issue"],
        })
        return

    print(f"Executing: removing partition field '{field_name}'...")
    with table.update_spec() as update:
        update.remove_field(field_name)

    executed_log.append({
        "action": "REMOVE_PARTITION_FIELD",
        "column": column,
        "field_removed": field_name,
        "issue_addressed": decision["issue"],
    })
    print(f"  -> Done. Removed partition field: {field_name}")

def handle_compact_files(table, decision, dry_run, preview_log, executed_log):
    if dry_run:
        print("Would run file compaction (rewrite small files into larger ones)")
        print(f"  -> Addresses issue: {decision['issue']}\n")
        preview_log.append({
            "action": "COMPACT_FILES",
            "issue_addressed": decision["issue"],
            "note": "Run with --execute to perform the actual rewrite",
        })
        return

    from compact_and_repartition import compact_table  # same folder as this file

    print("Executing: compacting and repartitioning table...")
    summary = compact_table(TABLE_NAME)

    executed_log.append({
        "action": "COMPACT_FILES",
        "issue_addressed": decision["issue"],
        "rows_rewritten": summary["rows_rewritten"],
        "file_count_after": summary["file_count_after"],
    })
    print(f"  -> Done. Rewrote {summary['rows_rewritten']} rows into {summary['file_count_after']} file(s).")

def handle_add_sort_order(table, decision, dry_run, preview_log, executed_log):
    column = decision["target_column"]

    current_sort = table.sort_order()
    existing_sort_columns = [f.source_id for f in current_sort.fields] if current_sort else []

    field = next((f for f in table.schema().fields if f.name == column), None)
    if field is None:
        print(f"Column '{column}' not found in schema — skipping")
        return

    if field.field_id in existing_sort_columns:
        print(f"Table is already sorted by '{column}' — skipping")
        return

    if dry_run:
        print(f"Would add sort order on '{column}'")
        print(f"  -> Addresses issue: {decision['issue']}\n")
        preview_log.append({
            "action": "ADD_SORT_ORDER",
            "column": column,
            "issue_addressed": decision["issue"],
            "note": "Sort order affects future writes/compactions, not existing files retroactively",
        })
        return

    print(f"Executing: adding sort order on '{column}'...")
    with table.update_sort_order() as update:
        update.asc(column, IdentityTransform(), NullOrder.NULLS_LAST)

    executed_log.append({
        "action": "ADD_SORT_ORDER",
        "column": column,
        "issue_addressed": decision["issue"],
        "note": "Applies to future writes/compactions — run compact_and_repartition.py to re-sort existing data",
    })
    print(f"  -> Done. New sort order set on: {column}")

ACTION_HANDLERS = {
    "REPARTITION_BY_COLUMN": handle_repartition,
    "REMOVE_PARTITION_FIELD": handle_remove_partition_field,
    "COMPACT_FILES": handle_compact_files,
    "ADD_SORT_ORDER": handle_add_sort_order,
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually apply the changes. Default is dry-run (preview only, no writes)."
    )
    args = parser.parse_args()
    dry_run = not args.execute

    catalog = load_catalog_conn()
    table = catalog.load_table(TABLE_NAME)

    with open("data/logs/agent_decisions.json") as f:
        decisions = json.load(f)

    print(f"Current partition spec: {table.spec()}\n")
    if dry_run:
        print("=== DRY RUN — no changes will be written. Pass --execute to apply. ===\n")

    executed_log = []
    preview_log = []

    for decision in decisions:
        action = decision["recommended_action"]

        if action == "NO_ACTION_NEEDED":
            print(f"No action needed for: {decision['issue']}")
            continue

        if action in COLUMN_REQUIRED_ACTIONS and not decision.get("target_column"):
            print(f"Skipping '{decision['issue']}' — action '{action}' requires a target_column but none was given")
            continue

        handler = ACTION_HANDLERS.get(action)
        if handler is None:
            print(f"Skipping '{decision['issue']}' — action '{action}' not yet implemented")
            continue

        handler(table, decision, dry_run, preview_log, executed_log)

    if dry_run:
        print(f"\nSpec unchanged (dry run): {table.spec()}\n")
        with open("data/logs/dry_run_preview.json", "w") as f:
            json.dump(preview_log, f, indent=2)
        print(f"Previewed {len(preview_log)} action(s). Details in data/logs/dry_run_preview.json")
        print("Run again with --execute to apply these changes.")
    else:
        print(f"\nUpdated partition spec: {table.spec()}\n")
        with open("data/logs/executed_actions.json", "w") as f:
            json.dump(executed_log, f, indent=2)
        print(f"Executed {len(executed_log)} action(s). Logged to data/logs/executed_actions.json")

if __name__ == "__main__":
    main()