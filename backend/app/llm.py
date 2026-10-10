import hashlib
import json
import os
import time

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, CHAT_MODEL

_client = genai.Client(api_key=GEMINI_API_KEY)
_RETRYABLE = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")

# Optional cache: same prompt → same answer, no API call. Enabled when LLM_CACHE is set to a file path.
_CACHE_FILE = os.getenv("LLM_CACHE")
_cache = {}
if _CACHE_FILE and os.path.exists(_CACHE_FILE):
    with open(_CACHE_FILE, encoding="utf-8") as f:
        _cache = json.load(f)


def _save_cache():
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False)


def _config(system):
    kwargs = dict(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=0,
    )
    if "2.5-flash" in CHAT_MODEL:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    return types.GenerateContentConfig(**kwargs)


def json_call(system, user, retries=3):
    """Send a prompt, get back (dict, milliseconds)."""
    key = hashlib.sha256(f"{CHAT_MODEL}|{system}|{user}".encode("utf-8")).hexdigest()
    if _CACHE_FILE and key in _cache:
        return _cache[key], 0

    for attempt in range(retries):
        try:
            t0 = time.perf_counter()
            resp = _client.models.generate_content(model=CHAT_MODEL, contents=user, config=_config(system))
            ms = int((time.perf_counter() - t0) * 1000)
            break
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg:
                raise RuntimeError(
                    f"Daily free-tier quota for {CHAT_MODEL} is used up. "
                    "Switch CHAT_MODEL in .env, enable billing, or wait for the reset."
                ) from None
            if attempt < retries - 1 and any(code in msg for code in _RETRYABLE):
                wait = 15 * (attempt + 1)
                print(f"   (Gemini busy or rate-limited, retrying in {wait}s)")
                time.sleep(wait)
                continue
            raise

    try:
        data = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError):
        data = {}
    if _CACHE_FILE:
        _cache[key] = data
        _save_cache()
    return data, ms