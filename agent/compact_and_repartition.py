"""
Rewrites all existing data in the sales table so it's physically
organized according to the new partition spec (vendor, order_date month).
This is the "real" compaction step — closes the gap between spec and data.
"""
from sentence_transformers import SentenceTransformer  # noop import, keeps safe order if extended later
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import AlwaysTrue

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

print(f"Partition spec: {table.spec()}")
print("Reading all existing data (805K rows)...")
df = table.scan().to_pandas()
print(f"Read {len(df)} rows")

# Same ns->us fix as before, in case dtype reverted on read
df["order_date"] = df["order_date"].astype("datetime64[us]")
arrow_table = pa.Table.from_pandas(df, schema=table.schema().as_arrow())

print("Rewriting data, organized by the new partition spec (this takes a bit for 805K rows)...")
table.overwrite(arrow_table, overwrite_filter=AlwaysTrue())

print("Done. Verifying new file layout...")
files = list(table.scan().plan_files())
print(f"Table now has {len(files)} data file(s) (was 1 before)")

# Show a few partition values to prove it worked
for f in files[:5]:
    print(f"  partition: {f.file.partition}")