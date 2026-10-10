import os
from dotenv import load_dotenv

load_dotenv()  # reads backend/.env

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(BACKEND_DIR, "kb")
CHROMA_DIR = os.path.join(BACKEND_DIR, "data", "chroma")
ASR_MODEL = os.getenv("ASR_MODEL", "")
TTS_VOICE = os.getenv("TTS_VOICE", "ur-PK-UzmaNeural")
AUDIO_DIR = os.path.join(BACKEND_DIR, "data", "audio")