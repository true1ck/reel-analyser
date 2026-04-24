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
import os
import sys
import importlib.util
from dotenv import load_dotenv

load_dotenv()

# Detect if MLX is available (typically only on macOS with Apple Silicon)
MLX_AVAILABLE = importlib.util.find_spec("mlx") is not None

# Cloud API Config
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
USE_NVIDIA_API = NVIDIA_API_KEY is not None

if USE_NVIDIA_API:
    # Use Cloud Model
    VISION_MODEL = "mistralai/mistral-small-4-119b-2603"
    # NVIDIA has their own high-speed ASR models like Parakeet or Whisper
    WHISPER_MODEL = "openai/whisper-large-v3"
elif MLX_AVAILABLE:
    # macOS / Apple Silicon optimized models
    VISION_MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
    WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
else:
    # Windows / Linux / CUDA / CPU models
    VISION_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"
    WHISPER_MODEL = "large-v3-turbo"  # for faster-whisper

# ─── PROCESSING ───────────────────────────────────────────────────────────────
MAX_TOKENS = 1024
TEMPERATURE = 0.2
REPETITION_PENALTY = 1.1
VIDEO_FPS = 1.0
MAX_PIXELS = 100352

# ─── SERVER ───────────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8080
FRONTEND_URL = "http://localhost:5173"
