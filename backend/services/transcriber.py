"""
Audio transcription service — wraps MLX Whisper for speech-to-text.
"""
from __future__ import annotations
from pathlib import Path

import mlx_whisper

from backend.config import WHISPER_MODEL


def transcribe_audio(audio_path: Path) -> str:
    """
    Transcribe and translate audio using MLX Whisper.
    
    Args:
        audio_path: Path to the WAV audio file.
    
    Returns:
        Translated English transcript string, or empty string if no audio.
    """
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        return ""

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=WHISPER_MODEL,
        task="translate",
    )
    return result["text"].strip()
