"""
Downloads the real "Online Retail II" dataset from the UCI Machine
Learning Repository — ~1M rows of real UK e-commerce transactions
(2009-2011). Saves a cleaned version to data/sample/sales.csv

Run with: python data/sample/download_public_dataset.py
"""
import urllib.request
import zipfile
import io
import pandas as pd

UCI_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"

print("Downloading dataset from UCI (this file is ~45MB, may take a minute)...")
with urllib.request.urlopen(UCI_URL) as response:
    zip_data = response.read()

print("Extracting...")
with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
    # The zip contains an Excel file with two sheets (2009-2010, 2010-2011)
    excel_filename = [n for n in z.namelist() if n.endswith(".xlsx")][0]
    with z.open(excel_filename) as f:
        excel_bytes = f.read()

print("Reading Excel sheets (this can take ~30s, it's a big file)...")
sheet1 = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=0)
sheet2 = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=1)
df = pd.concat([sheet1, sheet2], ignore_index=True)

# --- Clean up column names and types to match our pipeline's expectations ---
df = df.rename(columns={
    "Invoice": "order_id",
    "StockCode": "product_id",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "order_date",
    "Price": "amount",
    "Customer ID": "customer_id",
    "Country": "vendor",   # reusing "vendor" as country of sale for our schema
})

# Drop rows with missing customer_id or cancelled orders (Invoice starting with 'C')
df = df.dropna(subset=["customer_id"])
df = df[~df["order_id"].astype(str).str.startswith("C")]

# Keep only the columns our pipeline uses, add a "category" placeholder
df["category"] = "Retail"
df = df[["order_id", "customer_id", "vendor", "category", "order_date", "amount", "quantity"]]

df.to_csv("data/sample/sales.csv", index=False)
print(f"\nSaved {len(df):,} real transaction rows to data/sample/sales.csv")
print(df.head())