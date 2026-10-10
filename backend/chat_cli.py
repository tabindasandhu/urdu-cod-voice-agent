from app import db
from app.agent import Call, CALLABLE_STATUSES

db.init_db()
for o in db.list_orders():
    print(f"  #{o['id']}  {o['customer_name']:<12} Rs {o['amount']:>6,}  {o['status']}")

while True:
    raw = input("\nOrder id to call: ").strip()
    order = db.get_order(int(raw)) if raw.isdigit() else None
    if order and order["status"] in CALLABLE_STATUSES:
        break
    print("Please type the number of an order that is PENDING, NEEDS_REVIEW or NOT_CONFIRMED.")

call = Call(int(raw))
print("\nAGENT:", call.start())

while not call.ended:
    text = input("\nYOU:   ").strip()
    if not text:
        continue
    r = call.handle(text)
    print(f"AGENT: {r['reply']}")
    print(f"       [intent={r['intent']}  llm={r['llm_ms']} ms]")

print(f"\n=== OUTCOME: {call.outcome} | needs review: {call.needs_review} ===")
if call.review_reasons:
    print("Reasons:", "; ".join(call.review_reasons))
if call.cancel_reason:
    print("Cancel reason:", call.cancel_reason)