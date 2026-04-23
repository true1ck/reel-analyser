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
    prompt_text = f"""You are an absolute expert video analyst and meticulous note-taker. I am providing you with an educational/tutorial Instagram Reel video file and its audio transcript. 

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
        max_tokens=1024,
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