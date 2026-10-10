import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import asr, db, tts
from app.agent import Call, CALLABLE_STATUSES
from app.config import AUDIO_DIR

os.makedirs(AUDIO_DIR, exist_ok=True)

# Calls currently in progress, kept in memory: call_id -> Call object
ACTIVE_CALLS: dict[int, Call] = {}

DEMO_ORDERS = [
    ("Ayesha Khan", "0300-1111111", "Lawn 3-piece suit (Firozi)", 4500, "Lahore", "House 12, Block C, Johar Town"),
    ("Fatima Ali", "0301-2222222", "Ready-to-wear kurta (M) x2", 7200, "Karachi", "Flat 5, Block 13, Gulshan-e-Iqbal"),
    ("Sana Riaz", "0302-3333333", "Embroidered formal suit", 15500, "Multan", "Street 4, Shah Rukn-e-Alam Colony"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    await asyncio.to_thread(asr.load_model)      # load Whisper once, at startup
    yield


app = FastAPI(title="Zari Collective COD Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],     # the React dev server (Phase 6)
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


# ---------- request shapes (validated automatically) ----------
class OrderIn(BaseModel):
    customer_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    items: str = Field(min_length=1)
    amount: int = Field(gt=0)
    city: str = Field(min_length=1)
    address: str = Field(min_length=1)


class StartCallIn(BaseModel):
    order_id: int


class TextTurnIn(BaseModel):
    text: str = Field(min_length=1)


# ---------- helpers ----------
async def _speak(call, text, idx):
    """Generate the agent's audio for turn idx and record its TTS time."""
    name = f"call{call.call_id}_t{idx}_agent.mp3"
    tts_ms = await tts.synthesize_async(text, os.path.join(AUDIO_DIR, name))
    db.set_turn_extra(call.call_id, idx, tts_ms=tts_ms, audio=name)
    return f"/audio/{name}", tts_ms


async def _take_turn(call_id, text, asr_ms=0, customer_audio=None):
    call = ACTIVE_CALLS.get(call_id)
    if call is None:
        raise HTTPException(404, "No active call with that id (it ended, or the server restarted)")
    try:
        r = await asyncio.to_thread(call.handle, text)
    except Exception as e:
        raise HTTPException(503, f"Agent brain unavailable: {e}")

    customer_idx, agent_idx = call.turn_idx - 2, call.turn_idx - 1
    db.set_turn_extra(call_id, customer_idx, asr_ms=asr_ms or None, audio=customer_audio)
    audio_url, tts_ms = await _speak(call, r["reply"], agent_idx)

    if call.ended:
        ACTIVE_CALLS.pop(call_id, None)
    return {
        "heard": text,
        "reply": r["reply"],
        "audio_url": audio_url,
        "intent": r["intent"],
        "ended": r["ended"],
        "outcome": r["outcome"],
        "needs_review": call.needs_review,
        "latency": {"asr_ms": asr_ms, "llm_ms": r["llm_ms"], "tts_ms": tts_ms,
                    "total_ms": asr_ms + r["llm_ms"] + tts_ms},
    }

from fastapi.responses import RedirectResponse


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")

# ---------- endpoints ----------
@app.get("/api/health")
def health():
    return {"ok": True, "active_calls": len(ACTIVE_CALLS)}


@app.get("/api/orders")
def list_orders():
    return db.list_orders()


@app.post("/api/orders", status_code=201)
def create_order(order: OrderIn):
    order_id = db.create_order(order.customer_name, order.phone, order.items,
                               order.amount, order.city, order.address)
    return db.get_order(order_id)


@app.post("/api/demo/orders", status_code=201)
def create_demo_orders():
    ids = [db.create_order(*o) for o in DEMO_ORDERS]
    return [db.get_order(i) for i in ids]


@app.post("/api/calls", status_code=201)
async def start_call(body: StartCallIn):
    order = db.get_order(body.order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    if order["status"] not in CALLABLE_STATUSES:
        raise HTTPException(409, f"Order is already {order['status']}")
    call = Call(body.order_id)
    ACTIVE_CALLS[call.call_id] = call
    greeting = call.start()
    audio_url, tts_ms = await _speak(call, greeting, call.turn_idx - 1)
    return {"call_id": call.call_id, "reply": greeting, "audio_url": audio_url,
            "latency": {"tts_ms": tts_ms}}


@app.post("/api/calls/{call_id}/text")
async def text_turn(call_id: int, body: TextTurnIn):
    """The customer's reply as typed text (for testing without a mic)."""
    return await _take_turn(call_id, body.text.strip())


@app.post("/api/calls/{call_id}/audio")
async def audio_turn(call_id: int, file: UploadFile = File(...)):
    """The customer's reply as a recording (from the browser mic)."""
    if call_id not in ACTIVE_CALLS:
        raise HTTPException(404, "No active call with that id")
    ext = os.path.splitext(file.filename or "")[1] or ".webm"
    name = f"call{call_id}_{uuid.uuid4().hex[:8]}_customer{ext}"
    path = os.path.join(AUDIO_DIR, name)
    with open(path, "wb") as f:
        f.write(await file.read())

    text, asr_ms = await asyncio.to_thread(asr.transcribe, path)
    if not text:
        return {"retry": True, "message": "No speech detected, please try again"}
    return await _take_turn(call_id, text, asr_ms, name)


@app.get("/api/calls")
def list_calls():
    calls = db.list_calls()
    for c in calls:
        c["active"] = c["id"] in ACTIVE_CALLS
    return calls


@app.get("/api/calls/{call_id}")
def call_detail(call_id: int):
    call = db.get_call(call_id)
    if call is None:
        raise HTTPException(404, "Call not found")
    turns = db.get_turns(call_id)
    for t in turns:
        t["retrieved"] = json.loads(t["retrieved"]) if t["retrieved"] else None
        t["audio_url"] = f"/audio/{t['audio']}" if t.get("audio") else None
    return {**call, "order": db.get_order(call["order_id"]),
            "active": call_id in ACTIVE_CALLS, "turns": turns}