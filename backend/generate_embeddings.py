"""
Loads receipt documents, generates sentence embeddings using a local,
free model (no API, no internet needed after first download).
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"   # must be set before torch loads

from sentence_transformers import SentenceTransformer
import json
import pandas as pd

print("Loading embedding model (first run downloads ~90MB, then cached)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

with open("data/sample/receipts.json") as f:
    receipts = json.load(f)

texts = [r["raw_text"] for r in receipts]
print(f"Embedding {len(texts)} documents locally...")
embeddings = model.encode(texts, show_progress_bar=True)

df = pd.DataFrame(receipts)
df["embedding"] = list(embeddings)

df.to_parquet("data/sample/receipts_embeddings.parquet")
print(f"\nSaved embeddings for {len(df)} receipts -> data/sample/receipts_embeddings.parquet")
print(f"Embedding dimension: {len(embeddings[0])}")