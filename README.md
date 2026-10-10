# Urdu COD Order-Confirmation Voice Agent

An AI calling agent that confirms cash-on-delivery orders **in Urdu** for a (fictional) Pakistani clothing brand.
It listens with my **fine-tuned Urdu Whisper** model, understands replies with **Gemini**, answers questions **only from approved company policies (RAG)**, speaks back with a Pakistani Urdu voice, and writes the outcome back to the orders database. Anything off-script is handed to a human.



---

## Why

Fake and refused cash-on-delivery orders are a real cost for Pakistani e-commerce, and confirming every order by phone is repetitive work. This project is a small, end-to-end version of an Urdu calling agent for that job, built around a speech model I fine-tuned myself.

## What happens on a call

1. The agent greets the customer in Urdu and reads out the order, amount and address.
2. The customer replies by voice; my fine-tuned Whisper transcribes it.
3. The agent works out what they meant: **confirm, cancel, change address, ask a question, ask for a person, or say goodbye**.
4. Questions are answered **only from the brand's policy documents** (RAG). If the answer isn't there, the agent forwards the question and flags the call for review.
5. The outcome is written back to the orders table, and every turn is logged with transcript, intent, sources, timings and recordings.

```
 Browser (React + TS) ──recording──►  ASR: fine-tuned Urdu Whisper (faster-whisper, int8, CPU)
         ▲                                          │
         │                                          ▼
   reply text + audio            State machine (code owns the flow and outcomes)
         │                         │              │                 │
   TTS: numbers → spoken Urdu    Gemini:        RAG: policy        SQLite: orders,
   edge-tts (+ gTTS fallback)    intent JSON    chunks in          calls, turns,
         ▲                       + answers      ChromaDB           timings, recordings
         └───────────────────────────────┘
```

## Design: the LLM suggests, the code decides

- Gemini does **two narrow jobs**: classify each reply into one of 8 intents (returned as JSON), and answer questions from retrieved policy text only.
- **Python owns the conversation**: a small state machine, validated LLM output, outcomes written by code, hard limits (8 turns; two "didn't understand" replies → human).
- The greeting, confirmations and goodbyes are **fixed, pre-approved Urdu lines**.
- Complaints and "talk to a person" are routed to a human **before** retrieval runs.

**Outcomes:** Confirmed · Cancelled (with reason) · Address updated · Needs review · Not confirmed. A call can end Confirmed and still be **flagged for review**, e.g. if the customer asked something the knowledge base couldn't answer.

## Results

| What | Result |
|---|---|
| Fine-tuned ASR, Whisper-small on FLEURS Urdu test (299 clips) | **WER 36.7% → 28.6%**, CER 13.7% → 10.1% |
| RAG retrieval, 17 questions in Urdu script, Roman Urdu and English | **Hit@1 94%, Hit@3 100%** |
| Hand-tested conversations | **7/7** correct outcomes |
| Automated scenario suite | 17 scenarios written; full run pending (free-tier quota) |
| ASR speed, laptop CPU, int8 | ~10 s of audio transcribed in 3.4 s |
| LLM step (Gemini Flash, thinking off) | ~1 s per reply; ~2 s when a RAG answer is needed |

**Finding: similarity thresholds alone aren't safe.** The gap between the weakest real question (0.633) and the strongest off-topic one (0.618) was only 0.015, and "Do you have a shop in Lahore?" retrieved the *About* chunk at 0.722 even though nothing mentions a shop. The agent therefore uses intent routing + a low score floor + an LLM grounding check (`answerable: true/false`), and forwards questions it can't answer.

## Tech stack

| Layer | Tools |
|---|---|
| Speech recognition | Fine-tuned Whisper-small → CTranslate2 int8, `faster-whisper` |
| Language model | Gemini 2.5 Flash / Flash-Lite (JSON output) |
| Retrieval | `gemini-embedding-001`, ChromaDB |
| Text-to-speech | `edge-tts` (ur-PK-UzmaNeural) with `gTTS` fallback, custom Urdu number normaliser (lakh/crore) |
| Backend | Python, FastAPI, SQLite |
| Frontend | React, TypeScript, Vite |

## Models

- Fine-tuned model: [tabindasandhu/whisper-small-urdu-fleurs](https://huggingface.co/tabindasandhu/whisper-small-urdu-fleurs)
- Fast CPU version (CTranslate2, int8): [tabindasandhu/whisper-small-urdu-ct2](https://huggingface.co/tabindasandhu/whisper-small-urdu-ct2)

## Project structure

```
backend/
  app/
    agent.py        state machine: the call logic
    llm.py          Gemini calls (JSON, retries, test cache)
    prompts.py      LLM instructions + fixed Urdu lines
    rag.py          chunking, embeddings, ChromaDB search
    asr.py          fine-tuned Whisper (faster-whisper)
    tts.py          Urdu TTS with fallback
    normalizer.py   numbers → spoken Urdu
    db.py           SQLite: orders, calls, turns
    main.py         FastAPI app
  kb/               the brand's policy documents (knowledge base)
  run_scenarios.py  automated conversation tests
  rag_eval.py       retrieval evaluation (Hit@1 / Hit@3)
  chat_cli.py       text-only call in the terminal
  voice_chat.py     spoken call in the terminal
frontend/
  src/              React + TypeScript: orders, call screen, call log
```

## Running locally

**Requirements:** Python 3.11+ (tested on 3.13), Node.js 20+, a free [Gemini API key](https://aistudio.google.com).

**Backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # macOS/Linux: cp .env.example .env, then add your Gemini key
python index_kb.py                  # build the knowledge-base index
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

**Frontend** (in a second terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 → **Add demo orders** → **Call**.

**Other scripts** (from `backend/`, with the venv active)
```bash
python rag_eval.py              # retrieval accuracy
python run_scenarios.py         # all scenario tests (or: python run_scenarios.py 6 17)
python chat_cli.py              # text-only call
python voice_chat.py            # spoken call with your microphone
```

## Configuration (`backend/.env`)

| Variable | Example |
|---|---|
| `GEMINI_API_KEY` | your key |
| `CHAT_MODEL` | `gemini-2.5-flash-lite` |
| `EMBED_MODEL` | `gemini-embedding-001` |
| `ASR_MODEL` | `tabindasandhu/whisper-small-urdu-ct2` |
| `TTS_VOICE` | `ur-PK-UzmaNeural` |

## Limitations and next steps

- The brand, orders and policies are fictional; "calls" happen in the browser, not over the phone network.
- The ASR model was trained and tested on FLEURS: read speech, female speakers only. Real conversational and male speech will be harder.
- `edge-tts` is an unofficial service (hence the gTTS fallback); production would use a paid TTS API.
- In-progress calls are held in memory and are lost on a server restart.
- Each turn runs ASR → LLM → TTS one after another; streaming would cut time to first audio.

Next: full scenario-suite pass rate, end-to-end latency per turn, cached audio for fixed lines, streaming.

## Acknowledgements

Google FLEURS dataset · OpenAI Whisper · faster-whisper / CTranslate2 · ChromaDB · edge-tts / gTTS · FastAPI · React