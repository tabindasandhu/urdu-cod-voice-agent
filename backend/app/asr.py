import time

from faster_whisper import WhisperModel

from app.config import ASR_MODEL

_model = None


def load_model():
    global _model
    if _model is None:
        if not ASR_MODEL:
            raise RuntimeError("Set ASR_MODEL in .env")
        t0 = time.perf_counter()
        _model = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8")
        print(f"   (ASR model loaded in {time.perf_counter() - t0:.1f}s)")
    return _model


def transcribe(audio):
    """audio = file path, or 16 kHz mono float32 numpy array. Returns (text, ms)."""
    model = load_model()
    t0 = time.perf_counter()
    segments, _info = model.transcribe(
        audio, language="ur", task="transcribe", beam_size=1,
        vad_filter=True, condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    return text, int((time.perf_counter() - t0) * 1000)