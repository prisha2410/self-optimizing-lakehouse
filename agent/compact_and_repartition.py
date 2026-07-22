"""
Rewrites all existing data in the sales table so it's physically
organized according to the new partition spec (vendor, order_date month).
This is the "real" compaction step — closes the gap between spec and data.
"""
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import AlwaysTrue

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

def compact_table(table_name="sales_db.sales"):
    """Rewrites all existing data so it's physically organized per the
    current partition spec. Returns a small summary dict for logging."""
    catalog = load_catalog_conn()
    table = catalog.load_table(table_name)

    print(f"Partition spec: {table.spec()}")
    print("Reading all existing data (805K rows)...")
    df = table.scan().to_pandas()
    print(f"Read {len(df)} rows")

    df["order_date"] = df["order_date"].astype("datetime64[us]")
    arrow_table = pa.Table.from_pandas(df, schema=table.schema().as_arrow())

    print("Rewriting data, organized by the current partition spec (this takes a bit for 805K rows)...")
    table.overwrite(arrow_table, overwrite_filter=AlwaysTrue())

    print("Done. Verifying new file layout...")
    files = list(table.scan().plan_files())
    print(f"Table now has {len(files)} data file(s)")

    partitions_sample = [str(f.file.partition) for f in files[:5]]
    for p in partitions_sample:
        print(f"  partition: {p}")

    return {
        "rows_rewritten": len(df),
        "file_count_after": len(files),
        "sample_partitions": partitions_sample,
    }

if __name__ == "__main__":
    compact_table()