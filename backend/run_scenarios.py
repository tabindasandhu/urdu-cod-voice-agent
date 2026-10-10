import os
import time
import sys

# Use a separate test database, wiped fresh on every run
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "test.db")
os.environ["DB_PATH"] = TEST_DB
os.environ.setdefault("LLM_CACHE", os.path.join(os.path.dirname(TEST_DB), "llm_cache.json"))
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from app import db                 # noqa: E402  (must be imported after DB_PATH is set)
from app.agent import Call         # noqa: E402

DELAY = float(os.getenv("TEST_DELAY", "4"))   # pause between turns, for the free-tier rate limit


def address_of(call):
    return db.get_order(call.order["id"])["address"]


def agent_said(call, text):
    return any(text in t for s, t in call.history if s == "agent")


SCENARIOS = [
    # ---- confirmations ----
    dict(name="Confirm in Urdu script", turns=["جی ہاں، کنفرم ہے"],
         outcome="CONFIRMED", review=False),
    dict(name="Confirm in English", turns=["Yes please, send it"],
         outcome="CONFIRMED", review=False),
    dict(name="Confirm with Punjabi mix", turns=["haan ji bhej deo, main ghar ai aan"],
         outcome="CONFIRMED", review=False),

    # ---- cancellations ----
    dict(name="Cancel with reason in one go", turns=["nahi chahiye, ghalti se order ho gaya tha"],
         outcome="CANCELLED", review=False,
         check=("cancel reason saved", lambda c: bool(c.cancel_reason))),
    dict(name="Cancel, then asked for reason", turns=["cancel kar dein", "paise nahi hain abhi"],
         outcome="CANCELLED", review=False,
         check=("cancel reason saved", lambda c: bool(c.cancel_reason))),
    dict(name="Ambiguous no, then cancel", turns=["nahi", "cancel", "bas zaroorat nahi rahi"],
         outcome="CANCELLED", review=False),
    dict(name="Cancel, then changes mind", turns=["cancel kar dein", "acha nahi, rehne dein, bhej dein"],
         outcome="CONFIRMED", review=False),

    # ---- address changes ----
    dict(name="Address change in two steps",
         turns=["address change karna hai", "House 45, Street 7, DHA Phase 5 Lahore", "haan sahi hai"],
         outcome="ADDRESS_UPDATED", review=False,
         check=("new address saved", lambda c: "DHA" in address_of(c))),
    dict(name="New address given in one sentence",
         turns=["mera naya address hai Flat 3, Gulberg III, Lahore, wahan bhej dein", "jee bilkul"],
         outcome="ADDRESS_UPDATED", review=False,
         check=("new address saved", lambda c: "Gulberg" in address_of(c))),
    dict(name="Address corrected after read-back",
         turns=["address change karna hai", "House 9, Model Town Lahore",
                "nahi ghalat hai, House 19, Model Town Lahore", "haan"],
         outcome="ADDRESS_UPDATED", review=False,
         check=("corrected address saved", lambda c: "19" in address_of(c))),

    # ---- questions (RAG) ----
    dict(name="KB question, then confirm",
         turns=["parcel khol ke check kar sakti hoon?", "acha theek hai, confirm"],
         outcome="CONFIRMED", review=False),
    dict(name="Confirm + question in one sentence",
         turns=["haan confirm hai, delivery charges kitne hain?"],
         outcome="CONFIRMED", review=False,
         check=("answer mentions Rs 250", lambda c: agent_said(c, "250"))),
    dict(name="Question in Urdu script, then confirm",
         turns=["ریفنڈ کتنے دن میں آتا ہے؟", "ٹھیک ہے کنفرم"],
         outcome="CONFIRMED", review=False),
    dict(name="Question not in KB is escalated",
         turns=["Lahore mein aap ki koi shop hai?", "chalo theek hai confirm"],
         outcome="CONFIRMED", review=True),

    # ---- escalation and endings ----
    dict(name="Complaint goes to a human",
         turns=["pichli dafa rider ne badtameezi ki thi, kisi insaan se baat karao"],
         outcome="NEEDS_REVIEW", review=True),
    dict(name="Off-topic twice", turns=["aaj mausam bohat acha hai", "cricket dekha aap ne?"],
         outcome="NEEDS_REVIEW", review=True),
    dict(name="Customer says goodbye", turns=["abhi busy hoon, Allah Hafiz"],
         outcome="NOT_CONFIRMED", review=False),
]


def run(scenario):
    order_id = db.create_order("Test Customer", "0300-0000000", "Lawn 3-piece suit", 4500,
                               "Lahore", "House 12, Block C, Johar Town")
    call = Call(order_id)
    log = [("agent", call.start())]
    latencies = []
    for text in scenario["turns"]:
        if call.ended:
            log.append(("note", f"call already ended; '{text}' not sent"))
            break
        r = call.handle(text)
        log += [("customer", f"{text}   [{r['intent']}]"), ("agent", r["reply"])]
        latencies.append(r["llm_ms"])
        time.sleep(DELAY)

    outcome = call.outcome if call.ended else "STILL_OPEN"
    problems = []
    if outcome != scenario["outcome"]:
        problems.append(f"outcome {outcome}, expected {scenario['outcome']}")
    if call.ended and call.needs_review != scenario["review"]:
        problems.append(f"needs_review {call.needs_review}, expected {scenario['review']}")
    if "check" in scenario:
        desc, fn = scenario["check"]
        if not fn(call):
            problems.append(f"check failed: {desc}")
    return problems, log, latencies


db.init_db()
first, last = 1, len(SCENARIOS)
if len(sys.argv) == 3:                       # e.g.  python run_scenarios.py 6 17
    first, last = int(sys.argv[1]), int(sys.argv[2])
selected = list(enumerate(SCENARIOS, 1))[first - 1:last]

passed, all_latencies = 0, []
print(f"Running scenarios {first}-{last} (about {DELAY:.0f}s pause per turn)...\n")
for i, s in selected:
    problems, log, lat = run(s)
    all_latencies += lat
    if not problems:
        passed += 1
        print(f"PASS  {i:2d}. {s['name']}")
    else:
        print(f"FAIL  {i:2d}. {s['name']}")
        for p in problems:
            print(f"        - {p}")
        for speaker, text in log:
            print(f"          {speaker:>8}: {text}")

n = len(selected)
print(f"\nPassed {passed}/{n} ({passed / n:.0%})")
if all_latencies:
    lat = sorted(all_latencies)
    print(f"LLM time per customer turn: median {lat[len(lat) // 2]} ms, max {lat[-1]} ms")