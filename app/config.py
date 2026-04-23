from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Optional: set COMMENTGEN_DATA_DIR=/var/lib/commentgen on servers where the
# app install dir is not writable (avoids "attempt to write a readonly database").
_data_dir = os.getenv("COMMENTGEN_DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir).resolve() if _data_dir else BASE_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = DATA_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "commentgen.db"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost").strip()
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "commentgen").strip()
