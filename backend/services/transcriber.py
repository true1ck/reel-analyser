import requests
import httpx
import asyncio
import importlib.util
from pathlib import Path

from backend.config import WHISPER_MODEL, USE_NVIDIA_API, NVIDIA_API_KEY

# Detect if MLX is available
MLX_AVAILABLE = importlib.util.find_spec("mlx") is not None

if not USE_NVIDIA_API:
    if MLX_AVAILABLE:
        import mlx_whisper
    else:
        import torch
        from faster_whisper import WhisperModel


# ─── GLOBAL WHISPER (loaded once) ─────────────────────────────────────────────
_whisper_model = None


def get_whisper():
    """Lazy-load and cache the whisper model."""
    if USE_NVIDIA_API:
        return None # API doesn't need local loading

    global _whisper_model
    if _whisper_model is None:
        if MLX_AVAILABLE:
            # MLX version doesn't need a persistent model object in the same way
            return None
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _whisper_model = WhisperModel(
                WHISPER_MODEL, 
                device=device, 
                compute_type="float16" if device == "cuda" else "int8"
            )
    return _whisper_model


async def transcribe_via_api(audio_path: Path) -> str:
    """Transcribe audio using NVIDIA NIM API with robust error handling."""
    if not NVIDIA_API_KEY:
        return ""
        
    print(f"[->] Attempting NVIDIA Cloud Transcription ({WHISPER_MODEL})...")
    
    # Try different possible NIM endpoints
    endpoints = [
        "https://ai.api.nvidia.com/v1/audio/transcriptions",
        "https://integrate.api.nvidia.com/v1/audio/transcriptions"
    ]
    
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
    }

    # Open file in binary mode
    with open(audio_path, "rb") as f:
        files = {
            "file": (audio_path.name, f, "audio/mpeg")
        }
        data = {
            "model": WHISPER_MODEL,
            "response_format": "json"
        }
        
        for url in endpoints:
            try:
                print(f"    Trying cloud endpoint: {url}...")
                # Use standard requests (synchronous) wrapped in run_in_executor
                import requests
                
                def make_request():
                    return requests.post(url, headers=headers, files=files, data=data, timeout=120)
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, make_request)
                    
                if response.status_code == 200:
                    res_json = response.json()
                    print(f"    [OK] Cloud transcription successful!")
                    return res_json.get("text", "").strip()
                elif response.status_code == 401:
                    print(f"    [!] Invalid NVIDIA API Key")
                    return ""
                else:
                    print(f"    [!] Cloud API returned {response.status_code} from {url}")
            except Exception as e:
                print(f"    [!] Cloud connection failed for {url}: {e}")
                if "10053" in str(e):
                    print("    [TIP] This error (WinError 10053) usually means your local Antivirus/Firewall blocked the upload.")
                
    return ""


def transcribe_audio(audio_path: Path) -> str:
    """
    Transcribe audio with API attempt and local fallback.
    """
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        return ""

    transcript = ""
    
    # 1. Try NVIDIA API if enabled
    if USE_NVIDIA_API:
        try:
            # Run async function in sync context for pipeline
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # This is tricky in FastAPI, but we'll try
                import nest_asyncio
                nest_asyncio.apply()
                transcript = loop.run_until_complete(transcribe_via_api(audio_path))
            else:
                transcript = asyncio.run(transcribe_via_api(audio_path))
        except Exception as e:
            print(f"[WARN] NVIDIA API Failed: {e}. Falling back to local...")

    # 2. If API failed or was disabled, use local
    if not transcript:
        fallback_model = "base" if WHISPER_MODEL == "openai/whisper-large-v3" else WHISPER_MODEL
        print(f"[->] Falling back to local transcription ({fallback_model})...")
        if MLX_AVAILABLE:
            result = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=fallback_model,
                task="translate",
            )
            transcript = result["text"].strip()
        else:
            try:
                from faster_whisper import WhisperModel; import torch; device = "cuda" if torch.cuda.is_available() else "cpu"; model = WhisperModel(fallback_model, device=device, compute_type="int8")
                segments, info = model.transcribe(
                    str(audio_path),
                    task="translate",
                    beam_size=5
                )
                transcript = " ".join([segment.text for segment in segments]).strip()
            except Exception as e:
                print(f"[ERROR] Local transcription failed: {e}")
                
    return transcript
