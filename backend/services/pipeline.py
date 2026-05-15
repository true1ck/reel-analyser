"""
Pipeline orchestrator — coordinates download → transcribe → analyze with progress callbacks.
"""
from __future__ import annotations
import asyncio
import time
from pathlib import Path
from typing import Callable

from backend.services.downloader import download_video, extract_audio
from backend.services.transcriber import transcribe_audio
from backend.services.analyzer import _run_vision_pass, _run_text_pass, extract_category
from backend.services.router import VideoRouter
from backend.services.strategy_factory import get_strategy_for_category


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
        self.view_count: int = 0
        self.like_count: int = 0
        self.share_count: int = 0
        self.comment_count: int = 0
        # New enriched fields
        self.play_count: int = 0
        self.owner_username: str | None = None
        self.owner_name: str | None = None
        self.owner_id: str | None = None
        self.duration_sec: float | None = None
        self.published_at: str | None = None
        self.hashtags_json: str = '[]'
        self.comments_json: str = '[]'


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
        video_path, metadata = await asyncio.to_thread(download_video, url, reel_id)
        result.video_path = video_path
        result.title = metadata.get("title", f"Video {reel_id}")
        result.view_count = metadata.get("view_count") or 0
        result.like_count = metadata.get("like_count") or 0
        result.share_count = metadata.get("share_count") or 0
        result.comment_count = metadata.get("comment_count") or 0
        result.play_count = metadata.get("play_count") or 0
        result.owner_username = metadata.get("owner_username")
        result.owner_name = metadata.get("owner_name")
        result.owner_id = metadata.get("owner_id")
        result.duration_sec = metadata.get("duration_sec")
        result.published_at = metadata.get("published_at")
        result.hashtags_json = metadata.get("hashtags_json", "[]")
        result.comments_json = metadata.get("comments_json", "[]")
        
        await _progress("downloading", 20, "Extracting audio...")

        # Step 1.5: Extract audio
        audio_path = await asyncio.to_thread(extract_audio, video_path)
        result.audio_path = audio_path
        await _progress("downloading", 30, "Download complete")

        # Step 2: Transcribe (30% → 50%)
        await _progress("transcribing", 35, "Transcribing audio with Whisper...")
        transcript = await asyncio.to_thread(transcribe_audio, audio_path)
        result.transcript = transcript
        await _progress("transcribing", 50, "Transcription complete")

        # Format metadata for the prompt
        import json
        meta_str = json.dumps(metadata, indent=2)

        # Step 3a: Visual Extraction — Pass 1 (50% → 75%)
        await _progress("analyzing", 52, "Classifying video content type...")
        transcript_text = transcript if transcript else "(No speech detected in audio)"
        
        category = await asyncio.to_thread(VideoRouter.classify, transcript_text, metadata)
        strategy = get_strategy_for_category(category)
        
        await _progress("analyzing", 55, f"Pass 1: Extracting visual details (Category: {category})...")
        ext_prompt = strategy.get_extraction_prompt()
        visual_observations = await asyncio.to_thread(_run_vision_pass, video_path, ext_prompt)
        await _progress("analyzing", 75, "Pass 1 complete — visual details extracted")

        # Step 3b: Synthesis — Pass 2 (75% → 95%)
        await _progress("analyzing", 78, f"Pass 2: Synthesizing notes from visuals + transcript...")

        # Step 3b.1: Quick Web Search (75% → 78%)
        await _progress("analyzing", 76, "Performing web search for tools and alternatives...")
        try:
            # Generate search queries for the tool AND its alternatives
            query_prompt = f"""Given this video title: '{result.title}', 
transcript: '{transcript_text[:1000]}', 
and visual observations: '{visual_observations[:1000]}'. 
Identify the primary topic, software, tool, or website discussed or shown. 
Generate exactly two search queries separated by a newline:
1. The exact name of the tool or main topic
2. Top free and paid alternatives or related context
Respond with ONLY the two queries on separate lines. DO NOT wrap in quotes, DO NOT use numbering like 1., just the raw search terms."""
            
            search_queries_raw = await asyncio.to_thread(_run_text_pass, query_prompt)
            # Clean up the output by stripping common list prefixes (1., -, *, etc)
            import re
            queries = []
            for q in search_queries_raw.split('\n'):
                cleaned = re.sub(r'^(\d+\.|\-|\*)\s*', '', q.strip()).strip('\'" \t')
                if cleaned and "Here are" not in cleaned and "Sure" not in cleaned:
                    queries.append(cleaned)
            
            # Search DDG for both queries
            from ddgs import DDGS
            web_context = ""
            with DDGS() as ddgs:
                for q in queries[:2]:  # Limit to 2 queries
                    try:
                        search_results = list(ddgs.text(q, max_results=3))
                        web_context += f"Searched for: '{q}'\nResults:\n"
                        for r in search_results:
                            web_context += f"- {r.get('title')}: {r.get('href')}\n  {r.get('body')}\n"
                        web_context += "\n"
                    except Exception as inner_e:
                        print(f"Failed searching for {q}: {inner_e}")
                        continue
        except Exception as e:
            print(f"Web search failed: {e}")
            web_context = "No web search results available."

        await _progress("analyzing", 78, "Pass 2: Synthesizing tutorial from visuals + transcript + web search...")

        synthesis_prompt = strategy.get_synthesis_prompt(
            metadata=meta_str,
            visual_observations=visual_observations,
            transcript=transcript_text,
            web_context=web_context,
        )
        analysis = await asyncio.to_thread(_run_text_pass, synthesis_prompt)
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
