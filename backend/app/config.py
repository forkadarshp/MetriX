import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "dummy_eleven_key")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "dummy_deepgram_key")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Directories and paths
DATA_DIR = Path("data")
STORAGE_AUDIO_DIR = Path("storage/audio")
STORAGE_TRANSCRIPTS_DIR = Path("storage/transcripts")
DB_PATH = DATA_DIR / "benchmark.db"


def ensure_directories() -> None:
    """Ensure required directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def debug_log(msg: str) -> None:
    """Temporary debug logger, routed through info level."""
    logger.info(f"DEBUG: {msg}")


