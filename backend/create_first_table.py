"""
Connects to the Iceberg REST catalog (running via Docker), creates a
namespace + table, and writes our sample sales data into it as an Iceberg table.

Run with: python backend/create_first_table.py
(run from the project root, so relative paths line up)
"""
import pandas as pd
from pyiceberg.catalog import load_catalog

# --- Connect to the Iceberg REST catalog running in Docker ---
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

# --- Create a namespace (like a schema/database) ---
NAMESPACE = "sales_db"
if NAMESPACE not in [ns[0] for ns in catalog.list_namespaces()]:
    catalog.create_namespace(NAMESPACE)
    print(f"Created namespace: {NAMESPACE}")
else:
    print(f"Namespace already exists: {NAMESPACE}")

# --- Load sample data ---
df = pd.read_csv("data/sample/sales.csv", parse_dates=["order_date"])
print(f"Loaded {len(df)} rows from sample CSV")

# --- Fix: cast to microsecond precision — Iceberg doesn't support nanosecond timestamps ---
df["order_date"] = df["order_date"].astype("datetime64[us]")

# --- Convert to PyArrow (Iceberg writes via Arrow) ---
import pyarrow as pa
arrow_table = pa.Table.from_pandas(df)

# --- Create the Iceberg table (drop first if it already exists, for reruns) ---
TABLE_NAME = f"{NAMESPACE}.sales"
if catalog.table_exists(TABLE_NAME):
    catalog.drop_table(TABLE_NAME)
    print(f"Dropped existing table: {TABLE_NAME}")

table = catalog.create_table(TABLE_NAME, schema=arrow_table.schema)
print(f"Created Iceberg table: {TABLE_NAME}")

# --- Write the data ---
table.append(arrow_table)
print(f"Wrote {len(df)} rows into {TABLE_NAME}")

# --- Quick sanity check: read it back ---
result = table.scan().to_pandas()
print("\nSanity check — first 5 rows read back from Iceberg:")
print(result.head())
print(f"\nTotal rows in table: {len(result)}")