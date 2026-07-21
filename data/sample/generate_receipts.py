"""
Generates synthetic receipt/invoice text documents to build and test
the multimodal ingestion + embedding pipeline quickly.
(Swap this for real scanned receipts later — same downstream code works.)
"""
import json
import random

random.seed(7)

vendors = ["Fresh Mart", "TechZone Electronics", "Cafe Bloom", "Urban Furnishings", "QuickPrint Stationery"]
categories = ["Groceries", "Electronics", "Food & Dining", "Furniture", "Office Supplies"]
items_by_category = {
    "Groceries": ["Milk 1L", "Bread", "Eggs (12)", "Rice 5kg", "Cooking Oil"],
    "Electronics": ["USB Cable", "Wireless Mouse", "HDMI Cable", "Power Bank", "Earphones"],
    "Food & Dining": ["Coffee", "Sandwich", "Pasta", "Salad", "Juice"],
    "Furniture": ["Office Chair", "Study Table", "Bookshelf", "Cushion", "Lamp"],
    "Office Supplies": ["Notebook", "Stapler", "Pen Pack", "Sticky Notes", "Printer Paper"],
}

receipts = []
for i in range(20):
    category = random.choice(categories)
    vendor = random.choice(vendors)
    items = random.sample(items_by_category[category], k=random.randint(2, 4))
    total = round(sum(random.uniform(50, 800) for _ in items), 2)
    date = f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

    receipt_text = (
        f"Receipt #{1000+i}\n"
        f"Vendor: {vendor}\n"
        f"Date: {date}\n"
        f"Items: {', '.join(items)}\n"
        f"Total: Rs. {total}\n"
    )

    receipts.append({
        "doc_id": f"RCPT-{1000+i}",
        "vendor": vendor,
        "category": category,
        "date": date,
        "total": total,
        "raw_text": receipt_text,
    })

with open("data/sample/receipts.json", "w") as f:
    json.dump(receipts, f, indent=2)

print(f"Generated {len(receipts)} synthetic receipts -> data/sample/receipts.json")
print(receipts[0]["raw_text"])