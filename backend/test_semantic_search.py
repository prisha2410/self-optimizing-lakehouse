"""
Tests semantic search over our receipt embeddings — proves the
"ask questions in plain English" piece of the multimodal pipeline works.
"""
from sentence_transformers import SentenceTransformer   # must import before numpy/pandas
import numpy as np
import pandas as pd

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

df = pd.read_parquet("data/sample/receipts_embeddings.parquet")
print(f"Loaded {len(df)} receipt embeddings\n")

def search(query, top_k=3):
    query_embedding = model.encode(query)
    embeddings_matrix = np.stack(df["embedding"].values)

    # cosine similarity
    similarities = embeddings_matrix @ query_embedding / (
        np.linalg.norm(embeddings_matrix, axis=1) * np.linalg.norm(query_embedding)
    )

    top_indices = np.argsort(similarities)[::-1][:top_k]

    print(f'Query: "{query}"')
    print("-" * 50)
    for idx in top_indices:
        row = df.iloc[idx]
        print(f"  [{similarities[idx]:.3f}] {row['doc_id']} — {row['vendor']} ({row['category']}) — Rs. {row['total']}")
    print()

# --- Try a few natural-language queries ---
search("electronics purchases")
search("food and coffee")
search("office furniture")