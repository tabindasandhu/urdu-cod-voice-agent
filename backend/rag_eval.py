from app.rag import search

# (question, the chunk that should answer it)
EVAL = [
    ("return kaise karun?", "returns#return-policy"),
    ("refund kitne din mein aata hai", "returns#refunds"),
    ("size chota nikla to badal sakte hain?", "returns#size-exchange"),
    ("کیا میں پارسل کھول کر چیک کر سکتی ہوں؟", "payment#opening-the-parcel"),
    ("delivery charges kitne hain", "delivery#delivery-charges"),
    ("کراچی میں ڈلیوری کتنے دن میں ہوگی", "delivery#delivery-time"),
    ("Do you deliver to Dubai?", "delivery#delivery-areas"),
    ("mera parcel kahan hai, track kaise karun", "delivery#order-tracking"),
    ("main kal ghar par nahi hoon, delivery aage kar dein", "delivery#rescheduling-delivery"),
    ("COD pe koi extra charge hai?", "payment#cash-on-delivery"),
    ("JazzCash se pehle payment kar sakti hoon?", "payment#online-payment"),
    ("aap log call kyun kar rahe hain?", "payment#why-we-confirm-cod-orders"),
    ("order cancel karna hai", "returns#cancelling-an-order"),
    ("medium size ka chest kitna hai", "products#ready-to-wear-kurtas"),
    ("kya aap gents kurta bhi bechte hain?", "products#what-we-do-not-sell"),
    ("آپ کا دفتر کب کھلتا ہے", "company#working-hours"),
    ("WhatsApp number kya hai", "company#contact"),
    ("bachon ke kapre milte hain?", "products#what-we-do-not-sell"),
    ("formal suit ka size exchange ho sakta hai?", "products#formal-wear"),
    ("پیسے واپس کیسے ملیں گے", "returns#refunds"),
]

OUT_OF_SCOPE = [
    "aaj cricket match kaun jeeta",
    "mujhe ghar ke liye loan chahiye",
    "Lahore ka mausam kaisa hai",
]

hit1 = hit3 = 0
in_scores = []
for q, expected in EVAL:
    results = search(q, k=3)
    ids = [r["id"] for r in results]
    in_scores.append(results[0]["score"])
    hit1 += ids[0] == expected
    hit3 += expected in ids
    if ids[0] != expected:
        print(f"MISS@1  {q!r}\n        expected {expected}, got {ids}")

n = len(EVAL)
print(f"\nHit@1: {hit1}/{n} = {hit1/n:.0%}")
print(f"Hit@3: {hit3}/{n} = {hit3/n:.0%}")
print(f"In-scope top scores:     min {min(in_scores):.3f}, avg {sum(in_scores)/n:.3f}")
oos = [search(q, k=1)[0]["score"] for q in OUT_OF_SCOPE]
print(f"Out-of-scope top scores: {[round(s, 3) for s in oos]}")