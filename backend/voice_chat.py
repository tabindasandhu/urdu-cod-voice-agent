import os
import wave

import numpy as np
import sounddevice as sd
from faster_whisper import decode_audio

from app import asr, db, tts
from app.agent import Call, CALLABLE_STATUSES
from app.config import AUDIO_DIR

os.makedirs(AUDIO_DIR, exist_ok=True)


def speak(text, name):
    path = os.path.join(AUDIO_DIR, f"{name}.mp3")
    ms = tts.synthesize(text, path)
    print(f"AGENT: {text}")
    audio = decode_audio(path, sampling_rate=24000)
    sd.play(audio, 24000)
    sd.wait()
    return ms


def listen():
    chunks = []

    def on_audio(indata, frames, time_info, status):
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=on_audio):
        input("\n🎙  Speak, then press Enter...")
    return np.concatenate(chunks)[:, 0] if chunks else np.zeros(0, dtype=np.float32)


def save_wav(audio, path):
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


db.init_db()
for o in db.list_orders():
    print(f"  #{o['id']}  {o['customer_name']:<12} Rs {o['amount']:>6,}  {o['status']}")
while True:
    raw = input("\nOrder id to call: ").strip()
    order = db.get_order(int(raw)) if raw.isdigit() else None
    if order and order["status"] in CALLABLE_STATUSES:
        break
    print("Please type the number of an open order.")

asr.load_model()
call = Call(int(raw))
print("\n--- Call started ---")
speak(call.start(), f"call{call.call_id}_t0_agent")

turn = 0
while not call.ended:
    audio = listen()
    if len(audio) < 0.3 * 16000:
        print("(too short, try again)")
        continue
    turn += 1
    save_wav(audio, os.path.join(AUDIO_DIR, f"call{call.call_id}_t{turn}_customer.wav"))

    text, asr_ms = asr.transcribe(audio)
    if not text:
        print("(didn't hear any speech, try again)")
        continue
    print(f"YOU (heard): {text}")

    r = call.handle(text)
    tts_ms = speak(r["reply"], f"call{call.call_id}_t{turn}_agent")
    total = asr_ms + r["llm_ms"] + tts_ms
    print(f"       [{r['intent']}]  ASR {asr_ms} + LLM {r['llm_ms']} + TTS {tts_ms} = {total} ms")

print(f"\n=== OUTCOME: {call.outcome} | needs review: {call.needs_review} ===")
print(f"Recordings saved in {AUDIO_DIR}")