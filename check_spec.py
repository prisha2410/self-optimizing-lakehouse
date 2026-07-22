"""
Quick sanity check after the PyIceberg upgrade — confirms the core APIs
this project depends on (spec, inspect.files, scan.plan_files) still work
before running the full agent pipeline again.
"""
from pyiceberg.catalog import load_catalog

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

print("spec:", table.spec())
print("files:", len(table.inspect.files().to_pandas()))
print("plan_files:", len(list(table.scan().plan_files())))