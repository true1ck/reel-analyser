#!/usr/bin/env python3
"""
Instagram Reel Analyzer (Native MLX-VLM Version)
=================================================
Uses yt-dlp, whisper, and Qwen2.5-VL via mlx-vlm (Apple Silicon Native) 
to analyze Instagram reels directly from video files without pre-extracting frames.

Setup (one time):
    brew install yt-dlp ffmpeg
    python -m venv venv
    ./venv/bin/pip install mlx-vlm qwen-vl-utils torchvision openai-whisper requests

Usage:
    ./venv/bin/python reel_analyser.py "https://www.instagram.com/reel/xxx"
"""

import sys
import shutil
import subprocess
from pathlib import Path

import requests
import mlx_whisper

from mlx_vlm import load, generate
from qwen_vl_utils import process_vision_info


# ─── CONFIG ────────────────────────────────────────────────────────────────────
VISION_MODEL    = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
WHISPER_MODEL   = "mlx-community/whisper-large-v3-turbo"
OUTPUT_DIR      = Path.home() / "Documents" / "Reel analyser "  # where downloaded files go
# ───────────────────────────────────────────────────────────────────────────────


def banner(msg: str):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print(f"{'─'*60}")


def check_dependencies():
    """Make sure all required tools are installed."""
    missing = []
    for tool in ["yt-dlp", "ffmpeg"]:
        if not shutil.which(tool):
            missing.append(tool)
    if missing:
        print(f"[ERROR] Missing tools: {', '.join(missing)}")
        print("Install with: brew install " + " ".join(missing))
        sys.exit(1)
    print("[✓] System dependencies found")


def download_reel(url: str, out_dir: Path) -> tuple[Path, str]:
    """Download Instagram reel, return (video_path, title)."""
    banner("Step 1/3 — Downloading reel")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "reel.%(ext)s")

    # 1. Get title
    title_res = subprocess.run(
        ["yt-dlp", "--get-title", "--no-playlist", url],
        capture_output=True, text=True
    )
    title = title_res.stdout.strip() or "Instagram Reel"

    # 2. Download
    result = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--output", out_template,
            "--merge-output-format", "mp4",
            url,
        ],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("[ERROR] yt-dlp failed:")
        print(result.stderr)
        sys.exit(1)

    video_files = list(out_dir.glob("reel.*"))
    if not video_files:
        print("[ERROR] No video file downloaded.")
        sys.exit(1)

    video_path = video_files[0]
    print(f"[✓] Downloaded: {video_path.name} | Title: {title}")
    return video_path, title


def extract_audio(video_path: Path, out_dir: Path) -> Path:
    """Extract audio track as WAV for Whisper."""
    audio_path = out_dir / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path),
         "-vn", "-ar", "16000", "-ac", "1",
         str(audio_path)],
        capture_output=True
    )
    return audio_path


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe and translate audio using MLX Whisper."""
    banner("Step 2/3 — Transcribing & Translating audio (MLX Whisper)")
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        print("[!] No audio or audio too short — skipping transcription")
        return ""

    print(f"[→] Transcribing with {WHISPER_MODEL}...")
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=WHISPER_MODEL,
        task="translate"
    )
    transcript = result["text"].strip()
    print(f"[✓] Transcript ({len(transcript)} chars): {transcript[:120]}{'...' if len(transcript) > 120 else ''}")
    return transcript


def analyze_with_native_qwen(video_path: Path, transcript: str, title: str) -> str:
    """Feed the entire video + transcript directly to Qwen2.5-VL using mlx-vlm."""
    banner("Step 3/3 — Analyzing full video natively with MLX Qwen2.5-VL")

    print("[→] Loading Qwen2.5-VL model (this might take a few seconds)...")
    model, processor = load(VISION_MODEL)
    print(f"[✓] Loaded {VISION_MODEL}")

    transcript_section = f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
    prompt_text = f"""You are an expert video analyst and comprehensive note-taker. I am providing you with a short-form video (Instagram Reel / YouTube Short / TikTok) and its audio transcript.

If the transcript is in Hindi, Urdu, Hinglish, or another language, TRANSLATE it and write your final notes ENTIRELY IN ENGLISH.

Video title/metadata: {title}{transcript_section}

─── CRITICAL INSTRUCTIONS ───
Your job is to create a comprehensive, structured breakdown of EVERYTHING discussed in this video so the reader NEVER needs to watch it again. You must capture ALL information — every category, every list, every comparison, every framework, every tip — with ZERO omissions.

─── STEP 1: IDENTIFY CONTENT TYPE ───
First, determine what kind of content this video is:
- **Tutorial/How-To**: Step-by-step instructions to accomplish a task
- **Strategy/Framework**: Presenting a framework, methodology, or structured approach
- **Categorization/Comparison**: Organizing things into categories, tiers, or ranked lists
- **Tips/Advice**: Collection of tips, hacks, or recommendations
- **Review/Opinion**: Reviewing a product, tool, or concept
- **Motivational/Storytelling**: Personal story, inspiration, or mindset content

─── STEP 2: OUTPUT THE ANALYSIS ───
Include ALL required sections, then ADD content-type-specific sections:

### 📊 Quick Overview
- **Content Type**: [Tutorial / Strategy / Categorization / Tips / Review / Motivational]
- **Target Audience**: [Who is this video for?]
- **Summary**: [2-3 sentence TL;DR capturing the core message and ALL major points]

### 🗣️ English Transcript (Full)
- Provide a COMPLETE, clean English translation of the spoken audio.
- Preserve ALL details. If the speaker lists items, list ALL of them. If they describe categories, capture EVERY category and EVERY item within each.

### 🛠️ Tools & Resources Mentioned
- List ALL software, websites, AI tools, plugins, or platforms shown or spoken about.
- If none, state "No specific tools or resources mentioned."

─── CONTENT-TYPE-SPECIFIC SECTIONS ───

**IF Tutorial/How-To:**

### 🪜 Exact Step-by-Step Tutorial
1. **[Action]**: Detailed explanation with exact specifics.
(Chronologically list EVERY action.)

### 💻 Prompts / Code Used
- EXACT text of any prompts, commands, or code shown/typed.

**IF Framework/Strategy/Categorization:**

### 🧩 Framework Breakdown
For EACH category/tier/stage, create a SEPARATE sub-section:

#### [Category/Stage Name]
- **Purpose / Goal**: What is this category for?
- **Characteristics**: Key traits or attributes
- **Recommended Content Types / Examples**: List EVERY specific example the creator mentions for THIS category
- **When to use**: Context or timing guidance

(Repeat for ALL categories. IMPORTANT: Map each item to EXACTLY the category the creator placed it in. Do NOT lump items together.)

### 📐 How They Relate
- Explain relationships between categories (progression, hierarchy, ratios).

**IF Tips/Advice:**

### 💎 Tips & Recommendations
1. **[Tip]**: Full explanation
(Number EVERY tip with ALL supporting details.)

**IF Review/Comparison:**

### ⚖️ Review / Comparison
- Pros, Cons, Verdict

─── ALWAYS INCLUDE ───

### 💡 Key Notes & Takeaways
- Most important actionable insights.
- Warnings, gotchas, or tips the creator shares.

### 🎯 Action Items
- Concrete next steps the viewer should take.

Be EXHAUSTIVE. Capture EVERY detail. The reader should get MORE value from your notes than from watching the video."""

    # Qwen-VL specific message format for video
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": f"file://{video_path.absolute()}",
                    "max_pixels": 100352,
                    "fps": 1.0,
                },
                {"type": "text", "text": prompt_text},
            ],
        }
    ]

    print(f"[→] Processing visual information... extracting frames intrinsically.")
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)

    print(f"[→] Starting analysis (may take 1-3 minutes depending on video length)...")
    output = generate(
        model=model,
        processor=processor,
        prompt=text,
        images=image_inputs,
        videos=video_inputs,
        max_tokens=2048,
        temperature=0.2,
        repetition_penalty=1.1,
        verbose=False
    )
    
    print("[✓] Analysis complete")
    return output


def save_report(analysis: str, transcript: str, url: str, out_dir: Path):
    """Save the full report as a text file."""
    report_path = out_dir / "native_report.md"
    with open(report_path, "w") as f:
        f.write(f"# Instagram Reel Analysis (Native MLX)\n\n")
        f.write(f"**URL:** {url}\n\n")
        f.write(f"---\n\n")
        f.write(f"## Analysis\n\n{analysis}\n\n")
        if transcript:
            f.write(f"---\n\n## Full Transcript\n\n{transcript}\n")
    return report_path


def main():
    if len(sys.argv) < 2:
        print("Usage: ./venv/bin/python analyze_reel.py <instagram_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"\n🎬 Instagram Reel Analyzer (Native MLX Video)")
    print(f"URL: {url}")

    # Setup
    check_dependencies()
    out_dir = OUTPUT_DIR / url.split("/reel/")[-1].split("/")[0].split("?")[0]
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pipeline
    video_path, title = download_reel(url, out_dir)

    print("\n  Step 1.5/3 — Extracting audio path")
    audio_path = extract_audio(video_path, out_dir)

    transcript = transcribe_audio(audio_path)
    
    # Native Video Pipeline
    analysis = analyze_with_native_qwen(video_path, transcript, title)

    # Output
    banner("Report")
    print(f"\n{analysis}\n")

    report_path = save_report(analysis, transcript, url, out_dir)
    print(f"\n[✓] Full report saved to: {report_path}")


if __name__ == "__main__":
    main()