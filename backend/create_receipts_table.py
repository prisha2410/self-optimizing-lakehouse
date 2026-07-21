"""
Writes receipt documents + their embeddings into Iceberg, so structured
(sales) and unstructured (receipts) data live in the same lakehouse.
"""
from sentence_transformers import SentenceTransformer  # unused here, but keeps import order safe if you extend this file
import pandas as pd
import pyarrow as pa
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

NAMESPACE = "sales_db"  # reuse same namespace as sales table

df = pd.read_parquet("data/sample/receipts_embeddings.parquet")
print(f"Loaded {len(df)} receipts with embeddings")

# Iceberg needs a fixed-size list type for embedding vectors, not raw numpy arrays
df["embedding"] = df["embedding"].apply(lambda x: x.tolist())

arrow_table = pa.Table.from_pandas(df)

TABLE_NAME = f"{NAMESPACE}.receipts"
if catalog.table_exists(TABLE_NAME):
    catalog.drop_table(TABLE_NAME)
    print(f"Dropped existing table: {TABLE_NAME}")

table = catalog.create_table(TABLE_NAME, schema=arrow_table.schema)
print(f"Created Iceberg table: {TABLE_NAME}")

table.append(arrow_table)
print(f"Wrote {len(df)} receipts into {TABLE_NAME}")

result = table.scan().to_pandas()
print(f"\nSanity check — total rows in table: {len(result)}")
print(result[["doc_id", "vendor", "category", "total"]].head())