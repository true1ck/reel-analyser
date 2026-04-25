"""
Pipeline orchestrator — coordinates download → transcribe → analyze with progress callbacks.
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable

from backend.services.downloader import download_video, extract_audio
from backend.services.transcriber import transcribe_audio
from backend.services.analyzer import _run_vision_pass, _run_text_pass, extract_category, EXTRACTION_PROMPT, SYNTHESIS_PROMPT


class PipelineResult:
    """Result of a complete pipeline run."""
    def __init__(self):
        self.video_path: Path | None = None
        self.audio_path: Path | None = None
        self.title: str = ""
        self.transcript: str = ""
        self.analysis_md: str = ""
        self.category: str = "Uncategorized"
        self.subcategory: str | None = None
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
        video_path, metadata = download_video(url, reel_id)
        result.video_path = video_path
        result.title = metadata.get("title", f"Video {reel_id}")
        await _progress("downloading", 20, "Extracting audio...")

        # Step 1.5: Extract audio
        audio_path = extract_audio(video_path)
        result.audio_path = audio_path
        await _progress("downloading", 30, "Download complete")

        # Step 2: Transcribe (30% → 50%)
        await _progress("transcribing", 35, "Transcribing audio with Whisper...")
        transcript = transcribe_audio(audio_path)
        result.transcript = transcript
        await _progress("transcribing", 50, "Transcription complete")

        # Step 3a: Visual Extraction — Pass 1 (50% → 75%)
        await _progress("analyzing", 55, "Pass 1: Extracting visual details from video frames...")
        visual_observations = _run_vision_pass(video_path, EXTRACTION_PROMPT)
        await _progress("analyzing", 75, "Pass 1 complete — visual details extracted")

        # Step 3b: Synthesis — Pass 2 (75% → 95%)
        await _progress("analyzing", 78, "Pass 2: Synthesizing tutorial from visuals + transcript...")
        transcript_text = transcript if transcript else "(No speech detected in audio)"
        
        # Format metadata for the prompt
        import json
        meta_str = json.dumps(metadata, indent=2)

        synthesis_prompt = SYNTHESIS_PROMPT.format(
            metadata=meta_str,
            visual_observations=visual_observations,
            transcript=transcript_text,
        )
        analysis = _run_text_pass(synthesis_prompt)
        result.analysis_md = analysis

        # Extract category from analysis
        cat, subcat = extract_category(analysis)
        result.category = cat
        result.subcategory = subcat
        await _progress("analyzing", 95, "Analysis complete")

        # Done
        result.processing_ms = int((time.time() - start_time) * 1000)
        await _progress("done", 100, "Done!")

    except Exception as e:
        result.error = str(e)
        result.processing_ms = int((time.time() - start_time) * 1000)
        await _progress("failed", 0, f"Error: {e}")

    return result
