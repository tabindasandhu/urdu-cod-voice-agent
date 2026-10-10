import os

import sounddevice as sd
from faster_whisper import decode_audio

from app import asr, tts
from app.config import AUDIO_DIR
from app.normalizer import for_speech

os.makedirs(AUDIO_DIR, exist_ok=True)


def play(path):
    audio = decode_audio(path, sampling_rate=24000)
    sd.play(audio, 24000)
    sd.wait()


line = ("السلام علیکم Ayesha Khan، میں زری کلیکشن سے سارہ بات کر رہی ہوں۔ "
        "آپ کے آرڈر کی رقم 4,500 روپے ہے۔ کیا میں آپ کا آرڈر کنفرم کر دوں؟")

print("Spoken version:", for_speech(line))
path = os.path.join(AUDIO_DIR, "test_tts.mp3")
print(f"TTS took {tts.synthesize(line, path)} ms, playing...")
play(path)

heard, ms = asr.transcribe(path)
print(f"\nASR heard the TTS ({ms} ms): {heard}")

input("\nPress Enter, then say a sentence in Urdu (you have 4 seconds)...")
rec = sd.rec(int(4 * 16000), samplerate=16000, channels=1, dtype="float32")
sd.wait()
audio = rec[:, 0]
print(f"Loudest point: {abs(audio).max():.3f}   (below 0.05 = too quiet or wrong mic)")
import soundfile as sf
sf.write(os.path.join(AUDIO_DIR, "mic_test.wav"), audio, 16000)
print("Saved your recording to data/audio/mic_test.wav, play it to check")
heard, ms = asr.transcribe(audio)
print(f"ASR heard you ({ms} ms): {heard}")