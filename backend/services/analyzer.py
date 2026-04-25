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


# ─── PASS 1: VISUAL EXTRACTION ──────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an expert video frame analyst with perfect vision. Your ONLY job is to describe exactly what you see in each frame of this video.

For EVERY distinct screen/scene in the video, describe:

1. **On-screen text**: Read ALL text verbatim — titles, labels, buttons, menus, headers, captions, overlay text, watermarks. Copy them EXACTLY as written.
2. **Code & terminals**: If any code editor, terminal, IDE, or command line is visible, transcribe the COMPLETE visible code/commands character-by-character. Note the language, file names, and any syntax visible.
3. **URLs & paths**: Read any URLs in browser bars, file paths in explorers, or links shown on screen.
4. **UI elements**: Describe what application/website is open, what buttons/menus are being clicked, what settings are being changed.
5. **Visual actions**: What is the cursor doing? What is being selected, typed, dragged, or clicked?
6. **Screen transitions**: Note when the screen changes to a different app, tab, or view.

Be EXHAUSTIVE. Read every pixel. Miss NOTHING. Output raw observations in chronological order.
Do NOT summarize, do NOT interpret, do NOT structure into steps — just describe what you see."""


# ─── PASS 2: SYNTHESIS ──────────────────────────────────────────────────────
SYNTHESIS_PROMPT = """You are an expert tutorial writer creating a comprehensive, actionable reference guide. I am giving you two sources of information about an educational/tutorial video, along with its metadata:

1. **VISUAL OBSERVATIONS** — A detailed frame-by-frame description of everything shown on screen.
2. **AUDIO TRANSCRIPT** — What was spoken in the video.
3. **METADATA** — Information about the video (title, uploader, description, tags, etc).

METADATA:
{metadata}

VISUAL OBSERVATIONS:
{visual_observations}

AUDIO TRANSCRIPT:
{transcript}

Using ALL sources, create a comprehensive tutorial breakdown so the reader does NOT need to watch the video.

If the transcript is in Hindi, Urdu, Hinglish, or another language, TRANSLATE it and write everything in ENGLISH.

You MUST use EXACTLY this Markdown structure (include ALL sections):

### 📂 CATEGORY: [Create a broad category] > [Create a specific subcategory]
*(Example: "Software Development > React UI" or "Marketing > Instagram Growth")*

### 📊 Quick Overview
- **Difficulty**: [Beginner / Intermediate / Advanced]
- **Time to Follow**: [estimated time to replicate the tutorial, e.g. "15-20 minutes"]
- **Summary**: [2-3 sentence TL;DR of what the tutorial teaches and the end result]

### 📋 Prerequisites
- List everything the user needs BEFORE starting (software to install, accounts to create, skills required, files to download).
- Be specific: include version numbers if visible, exact tool names, OS requirements.

### 🗣️ English Transcript Translation
- Provide a full, clean English translation of the spoken audio. Capture every instruction and detail.

### 🛠️ Tools & Resources Mentioned
- List ALL software, websites, AI tools, plugins, extensions, or platforms shown on screen OR spoken about.
- Include version numbers, specific model names, or URLs if they were visible.

### 🪜 Exact Step-by-Step Tutorial
1. **[Specific Action]**: Detailed explanation with exact UI paths, button names, and settings. (e.g., "Click File → Settings → Extensions → Search for 'Playwright' → Install")
2. **[Specific Action]**: ...
(Chronologically list EVERY action. Reference exact text/code/URLs you saw on screen. Be extremely specific — the user should be able to follow this without the video.)

### 💻 Prompts / Code Used
- Write out the EXACT text of any prompts, commands, code snippets, or configurations shown or typed in the video.
- Use code blocks with the correct language for syntax highlighting.
- If multiple code snippets were shown, list them all in order.

### ✅ Quick Checklist
- [ ] [First actionable item the user should complete]
- [ ] [Second actionable item]
- [ ] [Continue for all major steps — the user can check these off as they follow along]

### 🔗 Related Resources
- List any URLs, documentation pages, GitHub repos, or search terms the viewer should look up.
- If URLs were visible on screen, include them verbatim.

### 💡 Key Notes & Takeaways
- Important warnings, prerequisites, gotchas, or tips.
- Any background context that helps understand why each step matters.
- Common mistakes to avoid.

Be precise, exhaustive, and reference specific things you observed on screen. The reader should be able to replicate the entire tutorial from your notes alone."""


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
    # ── Pass 1: Visual Extraction (model looks at video) ──
    visual_observations = _run_vision_pass(video_path, EXTRACTION_PROMPT)

    # ── Pass 2: Synthesis (text-only reasoning over extracted info) ──
    transcript_text = transcript if transcript else "(No speech detected in audio)"

    synthesis_prompt = SYNTHESIS_PROMPT.format(
        title=title,
        visual_observations=visual_observations,
        transcript=transcript_text,
    )

    analysis = _run_text_pass(synthesis_prompt)

    # ── Extract category from the analysis ──
    category = extract_category(analysis)

    return analysis, category
