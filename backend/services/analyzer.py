"""
Vision analysis service — wraps Qwen2.5-VL via mlx-vlm for video understanding.

Key design decisions:
  - Model & processor loaded ONCE and kept in memory (avoids ~10s reload per job).
  - Two-pass analysis: Pass 1 extracts raw visual details at high fidelity,
    Pass 2 synthesizes structured tutorial notes from visuals + transcript.
  - Auto-categorization is extracted from the synthesis output.
  - This separation of perception from reasoning dramatically improves
    on-screen text reading, code extraction, and step completeness.
"""
from __future__ import annotations
import re
from pathlib import Path

from mlx_vlm import load, generate
from qwen_vl_utils import process_vision_info

from backend.config import (
    VISION_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    REPETITION_PENALTY,
    VIDEO_FPS,
    MAX_PIXELS,
)


# ─── VALID CATEGORIES ────────────────────────────────────────────────────────
# (Removed predefined categories to allow dynamic categorization)


# ─── GLOBAL MODEL (loaded once, reused across all jobs) ──────────────────────
_model = None
_processor = None


def get_model():
    """Lazy-load and cache the vision model."""
    global _model, _processor
    if _model is None:
        _model, _processor = load(VISION_MODEL)
    return _model, _processor


from backend.services.router import VideoRouter
from backend.services.strategy_factory import get_strategy_for_category


def _run_vision_pass(video_path: Path, prompt: str) -> str:
    """Run a single vision model pass on the video."""
    model, processor = get_model()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": f"file://{video_path.absolute()}",
                    "max_pixels": MAX_PIXELS,
                    "fps": VIDEO_FPS,
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)

    output = generate(
        model=model,
        processor=processor,
        prompt=text,
        images=image_inputs,
        videos=video_inputs,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        repetition_penalty=REPETITION_PENALTY,
        verbose=False,
    )

    return output


def _run_text_pass(prompt: str) -> str:
    """Run a text-only synthesis pass (no video input)."""
    model, processor = get_model()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    output = generate(
        model=model,
        processor=processor,
        prompt=text,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        repetition_penalty=REPETITION_PENALTY,
        verbose=False,
    )

    return output


def extract_category(analysis_md: str) -> tuple[str, str | None]:
    """Parse the dynamic category and subcategory from the analysis markdown output."""
    # Look for the CATEGORY line: ### 📂 CATEGORY: Software Development > React UI
    match = re.search(
        r"###\s*📂\s*CATEGORY:\s*([^\n]+)",
        analysis_md,
        re.IGNORECASE,
    )
    if match:
        raw_cat = match.group(1).strip()
        parts = raw_cat.split(">", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        else:
            return parts[0].strip(), None
    return "Uncategorized", None


def analyze_video(video_path: Path, transcript: str, title: str) -> tuple[str, str]:
    """
    Analyze a video file using a two-pass approach with Qwen2.5-VL.
    
    Pass 1 (Vision): Extract raw visual observations from the video frames.
    Pass 2 (Synthesis): Combine visual observations + transcript into structured notes.
    
    Args:
        video_path: Path to the MP4 video file.
        transcript: English transcript of the audio.
        title: Title/metadata of the reel.
    
    Returns:
        Tuple of (markdown_analysis, category).
    """
    # ── Pass 0: Classify Content ──
    transcript_text = transcript if transcript else "(No speech detected in audio)"
    metadata = {"title": title}
    import json
    metadata_str = json.dumps(metadata)
    
    category = VideoRouter.classify(transcript_text, metadata)
    strategy = get_strategy_for_category(category)

    # ── Pass 1: Visual Extraction (model looks at video) ──
    visual_observations = _run_vision_pass(video_path, strategy.get_extraction_prompt())

    # ── Pass 2: Synthesis (text-only reasoning over extracted info) ──
    synthesis_prompt = strategy.get_synthesis_prompt(
        metadata=metadata_str,
        visual_observations=visual_observations,
        transcript=transcript_text,
        web_context="No web search results available.", # Fallback since this is a helper
    )

    analysis = _run_text_pass(synthesis_prompt)

    # ── Extract category from the analysis ──
    category = extract_category(analysis)

    return analysis, category
