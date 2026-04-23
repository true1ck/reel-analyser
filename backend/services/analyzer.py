"""
Vision analysis service — wraps Qwen2.5-VL via mlx-vlm for video understanding.

Key design decision: the model and processor are loaded ONCE and kept in memory
to avoid the expensive reload cost (~10s) per analysis.
"""
from __future__ import annotations
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


# ─── GLOBAL MODEL (loaded once, reused across all jobs) ──────────────────────
_model = None
_processor = None


def get_model():
    """Lazy-load and cache the vision model."""
    global _model, _processor
    if _model is None:
        _model, _processor = load(VISION_MODEL)
    return _model, _processor


ANALYSIS_PROMPT = """You are an absolute expert video analyst and meticulous note-taker. I am providing you with an educational/tutorial Instagram Reel video file and its audio transcript. 

If the transcript is in Hindi, Urdu, or another language, TRANSLATE it mentally and write your final notes ENTIRELY IN ENGLISH.

Reel title/metadata: {title}{transcript_section}

Please provide a highly practical, step-by-step breakdown of the tutorial so the user does NOT have to watch the video again.

You MUST use exactly this Markdown structure:

### 🗣️ English Transcript Translation
- Provide a full, clean English translation of the spoken audio transcript.

### 🛠️ Tools & Resources Mentioned
- List all software, websites, AI tools, or plugins shown or spoken about (e.g., Playwright, Claude, MCP, specific folders).

### 🪜 Exact Step-by-Step Tutorial
1. **[Action Name]**: Detailed explanation of the action. (e.g., "Install Playwright MCP inside Claude", "Open the Reference Folder").
2. **[Action Name]**: ...
(Make sure to chronologically list every single action the creator takes or instructs the viewer to take).

### 💻 Prompts / Code Used
- Write out any specific text prompts, commands, or code snippets the creator pastes or types in the video.

### 💡 Key Notes & Takeaways
- Any important warnings, background contexts, or tips the creator shares to make it work.

Be precise, highly specific, and output only the required markdown structure."""


def analyze_video(video_path: Path, transcript: str, title: str) -> str:
    """
    Analyze a video file using Qwen2.5-VL with the audio transcript.
    
    Args:
        video_path: Path to the MP4 video file.
        transcript: English transcript of the audio.
        title: Title/metadata of the reel.
    
    Returns:
        Markdown analysis string.
    """
    model, processor = get_model()

    transcript_section = (
        f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
    )
    prompt_text = ANALYSIS_PROMPT.format(
        title=title, transcript_section=transcript_section
    )

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
                {"type": "text", "text": prompt_text},
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
