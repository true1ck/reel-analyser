"""
Centralized configuration for the Reel Analyser backend.
"""
from pathlib import Path

# ─── PATHS ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REELS_DIR = DATA_DIR / "reels"
DB_PATH = DATA_DIR / "reel_analyser.db"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
REELS_DIR.mkdir(parents=True, exist_ok=True)

# ─── ML MODELS ────────────────────────────────────────────────────────────────
VISION_MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

# ─── PROCESSING ───────────────────────────────────────────────────────────────
MAX_TOKENS = 4096
TEMPERATURE = 0.1
REPETITION_PENALTY = 1.1
VIDEO_FPS = 2.0
MAX_PIXELS = 602112

# ─── SERVER ───────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
FRONTEND_URL = "http://localhost:5173"
