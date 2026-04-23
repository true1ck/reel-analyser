"""
Pipeline orchestrator — coordinates download → transcribe → analyze with progress callbacks.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable

from backend.services.downloader import download_video, extract_audio
from backend.services.transcriber import transcribe_audio
from backend.services.analyzer import analyze_video


class PipelineResult:
    """Result of a complete pipeline run."""
    def __init__(self):
        self.video_path: Path | None = None
        self.audio_path: Path | None = None
        self.title: str = ""
        self.transcript: str = ""
        self.analysis_md: str = ""
        self.processing_ms: int = 0
        self.error: str | None = None


async def run_pipeline(
    url: str,
    reel_id: str,
    on_progress: Callable | None = None,
) -> PipelineResult:
    """
    Run the full analysis pipeline for a single reel.

    Args:
        url: Instagram reel URL.
        reel_id: Extracted reel ID.
        on_progress: Optional async callback(status, progress_pct, current_step).

    Returns:
        PipelineResult with all outputs.
    """
    result = PipelineResult()
    start_time = time.time()

    async def _progress(status: str, pct: int, step: str):
        if on_progress:
            await on_progress(status, pct, step)

    try:
        # Step 1: Download (0% → 30%)
        await _progress("downloading", 5, "Starting download...")
        video_path, title = download_video(url, reel_id)
        result.video_path = video_path
        result.title = title
        await _progress("downloading", 20, "Extracting audio...")

        # Step 1.5: Extract audio
        audio_path = extract_audio(video_path)
        result.audio_path = audio_path
        await _progress("downloading", 30, "Download complete")

        # Step 2: Transcribe (30% → 55%)
        await _progress("transcribing", 35, "Transcribing audio with Whisper...")
        transcript = transcribe_audio(audio_path)
        result.transcript = transcript
        await _progress("transcribing", 55, "Transcription complete")

        # Step 3: Analyze (55% → 95%)
        await _progress("analyzing", 60, "Loading vision model...")
        analysis = analyze_video(video_path, transcript, title)
        result.analysis_md = analysis
        await _progress("analyzing", 95, "Analysis complete")

        # Done
        result.processing_ms = int((time.time() - start_time) * 1000)
        await _progress("done", 100, "Done!")

    except Exception as e:
        result.error = str(e)
        result.processing_ms = int((time.time() - start_time) * 1000)
        await _progress("failed", 0, f"Error: {e}")

    return result
