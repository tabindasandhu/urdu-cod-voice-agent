import asyncio
import time

import edge_tts
from gtts import gTTS

from app.config import TTS_VOICE
from app.normalizer import for_speech


async def _edge(text, path):
    await edge_tts.Communicate(text, TTS_VOICE).save(path)


def _google(text, path):
    gTTS(text=text, lang="ur").save(path)


async def synthesize_async(text, path):
    """Text -> MP3 file. Tries edge-tts first, falls back to gTTS. Returns milliseconds."""
    spoken = for_speech(text)
    t0 = time.perf_counter()
    try:
        await _edge(spoken, path)
    except Exception as e:
        print(f"   (edge-tts failed: {type(e).__name__}, using Google TTS instead)")
        await asyncio.to_thread(_google, spoken, path)
    return int((time.perf_counter() - t0) * 1000)


def synthesize(text, path):
    return asyncio.run(synthesize_async(text, path))