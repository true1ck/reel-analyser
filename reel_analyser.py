import os
import sys
import shutil
import subprocess
import importlib.util
import base64
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# Detect if MLX is available
MLX_AVAILABLE = importlib.util.find_spec("mlx") is not None

# Cloud API Config
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
USE_NVIDIA_API = NVIDIA_API_KEY is not None

if USE_NVIDIA_API:
    VISION_MODEL    = "mistralai/mistral-small-4-119b-2603"
    WHISPER_MODEL   = "large-v3-turbo"
elif MLX_AVAILABLE:
    import mlx_whisper
    from mlx_vlm import load, generate
    VISION_MODEL    = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
    WHISPER_MODEL   = "mlx-community/whisper-large-v3-turbo"
else:
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from faster_whisper import WhisperModel
    VISION_MODEL    = "Qwen/Qwen2.5-VL-7B-Instruct"
    WHISPER_MODEL   = "large-v3-turbo"

from qwen_vl_utils import process_vision_info

OUTPUT_DIR      = Path.home() / "Documents" / "Reel-Analyser"  # where downloaded files go
# ───────────────────────────────────────────────────────────────────────────────


def banner(msg: str):
    print(f"\n{'-'*60}")
    print(f"  {msg}")
    print(f"{'-'*60}")


# ─── TOOL PATHS ───────────────────────────────────────────────────────────────
YT_DLP_PATH = "yt-dlp"
FFMPEG_PATH = "ffmpeg"

def check_dependencies():
    """Make sure all required tools are installed and store their paths."""
    global YT_DLP_PATH, FFMPEG_PATH
    missing = []
    
    # On Windows, yt-dlp might be in venv/Scripts and not in system PATH
    venv_scripts = Path(__file__).resolve().parent / "venv" / "Scripts"
    
    # Check yt-dlp
    found_yt = shutil.which("yt-dlp")
    if not found_yt and sys.platform == "win32":
        found_yt = shutil.which("yt-dlp", path=str(venv_scripts))
    if found_yt:
        YT_DLP_PATH = found_yt
    else:
        missing.append("yt-dlp")
        
    # Check ffmpeg
    found_ff = shutil.which("ffmpeg")
    if found_ff:
        FFMPEG_PATH = found_ff
    else:
        missing.append("ffmpeg")
            
    if missing:
        print(f"[ERROR] Missing tools: {', '.join(missing)}")
        if sys.platform == "darwin":
            print("Install with: brew install yt-dlp ffmpeg")
        else:
            print("Install with: pip install yt-dlp (and ensure ffmpeg is in PATH)")
        sys.exit(1)
    print("[OK] System dependencies found")


def download_reel(url: str, out_dir: Path) -> tuple[Path, str]:
    """Download Instagram reel, return (video_path, title)."""
    banner("Step 1/3 - Downloading reel")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "reel.%(ext)s")

    # 1. Get title
    title_res = subprocess.run(
        [YT_DLP_PATH, "--get-title", "--no-playlist", url],
        capture_output=True, text=True
    )
    title = title_res.stdout.strip() or "Instagram Reel"

    # 2. Download
    result = subprocess.run(
        [
            YT_DLP_PATH,
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
    print(f"[OK] Downloaded: {video_path.name} | Title: {title}")
    return video_path, title


def extract_audio(video_path: Path, out_dir: Path) -> Path:
    """Extract audio track as WAV for Whisper."""
    audio_path = out_dir / "audio.wav"
    subprocess.run(
        [FFMPEG_PATH, "-y", "-i", str(video_path),
         "-vn", "-ar", "16000", "-ac", "1",
         str(audio_path)],
        capture_output=True
    )
    return audio_path


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe and translate audio using the best available backend."""
    banner(f"Step 2/3 - Transcribing & Translating audio ({'NVIDIA API' if USE_NVIDIA_API else 'MLX Whisper' if MLX_AVAILABLE else 'Faster Whisper'})")
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        print("[!] No audio or audio too short - skipping transcription")
        return ""

    print(f"[->] Transcribing with {WHISPER_MODEL}...")
    
    if USE_NVIDIA_API:
        invoke_url = "https://integrate.api.nvidia.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"}
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data = {"model": WHISPER_MODEL, "response_format": "json"}
            response = requests.post(invoke_url, headers=headers, files=files, data=data)
        if response.status_code != 200:
            print(f"[ERROR] API Error: {response.text}")
            return ""
        transcript = response.json().get("text", "").strip()
    elif MLX_AVAILABLE:
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=WHISPER_MODEL,
            task="translate"
        )
        transcript = result["text"].strip()
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = WhisperModel(WHISPER_MODEL, device=device, compute_type="float16" if device == "cuda" else "int8")
        segments, info = model.transcribe(str(audio_path), task="translate")
        transcript = " ".join([segment.text for segment in segments]).strip()
    
    print(f"[OK] Transcript ({len(transcript)} chars): {transcript[:120]}{'...' if len(transcript) > 120 else ''}")
    return transcript


def analyze_with_native_qwen(video_path: Path, transcript: str, title: str) -> str:
    """Feed the entire video + transcript directly to Qwen2.5-VL or NVIDIA API."""
    if USE_NVIDIA_API:
        banner(f"Step 3/3 - Analyzing via NVIDIA API ({VISION_MODEL})")
        print(f"[->] Calling NVIDIA NIM API...")
        
        invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        transcript_section = f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
        prompt_text = f"Analyze this reel titled '{title}'. {transcript_section}\n\nPlease provide a step-by-step tutorial based on the transcript."
        
        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": VISION_MODEL,
            "messages": [{"role": "user", "content": prompt_text}],
            "max_tokens": 1024,
            "temperature": 0.2,
            "reasoning_effort": "high" if "mistral-small" in VISION_MODEL else None
        }
        
        response = requests.post(invoke_url, headers=headers, json=payload)
        if response.status_code != 200:
            return f"API Error: {response.text}"
        
        return response.json()["choices"][0]["message"]["content"]

    banner(f"Step 3/3 - Analyzing full video natively ({'MLX' if MLX_AVAILABLE else 'Transformers'})")
    print(f"[->] Loading Qwen2.5-VL model...")
    
    if MLX_AVAILABLE:
        model, processor = load(VISION_MODEL)
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        load_kwargs = {
            "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
            "device_map": "auto",
        }
        if device == "cuda":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(VISION_MODEL, **load_kwargs)
        processor = AutoProcessor.from_pretrained(VISION_MODEL)
    
    print(f"[OK] Loaded {VISION_MODEL}")

    transcript_section = f"\n\nAUDIO TRANSCRIPT:\n{transcript}" if transcript else "\n\n(No speech detected)"
    prompt_text = f"""You are an absolute expert video analyst and meticulous note-taker. I am providing you with an educational/tutorial Instagram Reel video file and its audio transcript. 

If the transcript is in Hindi, Urdu, or another language, TRANSLATE it mentally and write your final notes ENTIRELY IN ENGLISH.

Reel title/metadata: {title}{transcript_section}

Please provide a highly practical, step-by-step breakdown of the tutorial so the user does NOT have to watch the video again.

You MUST use exactly this Markdown structure:

### English Transcript Translation
- Provide a full, clean English translation of the spoken audio transcript.

### Tools & Resources Mentioned
- List all software, websites, AI tools, or plugins shown or spoken about (e.g., Playwright, Claude, MCP, specific folders).

### Exact Step-by-Step Tutorial
1. **[Action Name]**: Detailed explanation of the action. (e.g., "Install Playwright MCP inside Claude", "Open the Reference Folder").
2. **[Action Name]**: ...
(Make sure to chronologically list every single action the creator takes or instructs the viewer to take).

### Prompts / Code Used
- Write out any specific text prompts, commands, or code snippets the creator pastes or types in the video.

### Key Notes & Takeaways
- Any important warnings, background contexts, or tips the creator shares to make it work.

Be precise, highly specific, and output only the required markdown structure."""

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "video",
                    "video": str(video_path.absolute()) if not MLX_AVAILABLE else f"file://{video_path.absolute()}",
                    "max_pixels": 100352,
                    "fps": 1.0,
                },
                {"type": "text", "text": prompt_text},
            ],
        }
    ]

    print(f"[->] Processing visual information...")
    
    if MLX_AVAILABLE:
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
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
    else:
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(model.device)

        print(f"[->] Starting analysis (may take 1-3 minutes)...")
        generated_ids = model.generate(**inputs, max_new_tokens=1024)
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
    
    print("[OK] Analysis complete")
    return output


def save_report(analysis: str, transcript: str, url: str, out_dir: Path) -> Path:
    """Save the final markdown report."""
    report_path = out_dir / "native_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Reel Analysis Report\n\n")
        f.write(f"**URL:** {url}\n")
        f.write(f"**Date:** {Path().cwd().name}\n\n")
        f.write(f"## Analysis\n\n")
        f.write(analysis)
        if transcript:
            f.write(f"\n\n---\n\n## Full Transcript\n\n{transcript}\n")
    return report_path


def main():
    if len(sys.argv) < 2:
        print("Usage: ./venv/bin/python analyze_reel.py <instagram_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"\n[Reel Analyzer] (Native Cross-Platform Video)")
    print(f"URL: {url}")

    # Setup
    check_dependencies()
    reel_id = url.split("/reel/")[-1].split("/")[0].split("?")[0]
    out_dir = OUTPUT_DIR / reel_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pipeline
    video_path, title = download_reel(url, out_dir)

    print("\n  Step 1.5/3 - Extracting audio path")
    audio_path = extract_audio(video_path, out_dir)

    transcript = transcribe_audio(audio_path)
    
    # Native Video Pipeline
    analysis = analyze_with_native_qwen(video_path, transcript, title)

    # Output
    banner("Report")
    print(f"\n{analysis}\n")

    report_path = save_report(analysis, transcript, url, out_dir)
    print(f"\n[OK] Full report saved to: {report_path}")


if __name__ == "__main__":
    main()