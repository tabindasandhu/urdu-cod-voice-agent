import json
import sqlite3
from app.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("ORDERS")
for o in conn.execute("SELECT * FROM orders"):
    print(f"  #{o['id']} {o['customer_name']:<12} {o['status']:<13} {o['address']}")

print("\nCALLS")
for c in conn.execute("SELECT * FROM calls ORDER BY id DESC LIMIT 5"):
    flag = "⚠ REVIEW" if c["needs_review"] else ""
    print(f"\n  Call {c['id']} (order #{c['order_id']}) → {c['outcome']} {flag}")
    print(f"  Summary: {c['summary']}")
    for t in conn.execute("SELECT * FROM turns WHERE call_id = ? ORDER BY idx", (c["id"],)):
        extra = f"  [{t['intent']}, {t['llm_ms']} ms]" if t["speaker"] == "customer" else (
        f"  [answer {t['llm_ms']} ms]" if t["llm_ms"] else "")
        print(f"    {t['speaker']:>8}: {t['text']}{extra}")
        if t["retrieved"]:
            r = json.loads(t["retrieved"])
            print(f"             RAG query: {r['query']} | used: {r['used']} | top: {r['hits'][:1]}")