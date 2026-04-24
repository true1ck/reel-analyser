import sys
import shutil
import subprocess
from pathlib import Path

from backend.config import REELS_DIR, PROJECT_ROOT


# ─── TOOL PATHS ───────────────────────────────────────────────────────────────
YT_DLP_PATH = "yt-dlp"
FFMPEG_PATH = "ffmpeg"

def _resolve_tools():
    """Locate tools and store their absolute paths."""
    global YT_DLP_PATH, FFMPEG_PATH
    
    # On Windows, yt-dlp might be in venv/Scripts
    venv_scripts = PROJECT_ROOT / "venv" / "Scripts"
    
    # Check yt-dlp
    found_yt = shutil.which("yt-dlp")
    if not found_yt and sys.platform == "win32":
        found_yt = shutil.which("yt-dlp", path=str(venv_scripts))
    if found_yt:
        YT_DLP_PATH = found_yt
        
    # Check ffmpeg
    found_ff = shutil.which("ffmpeg")
    if found_ff:
        FFMPEG_PATH = found_ff

# Initialize tool paths
_resolve_tools()


def check_dependencies() -> list[str]:
    """Check for required system tools. Returns list of missing tools."""
    missing = []
    if not shutil.which(YT_DLP_PATH) and not Path(YT_DLP_PATH).is_file():
        missing.append("yt-dlp")
    if not shutil.which(FFMPEG_PATH) and not Path(FFMPEG_PATH).is_file():
        missing.append("ffmpeg")
    return missing


def download_video(url: str, video_id: str) -> tuple[Path, str]:
    """
    Download a video from Instagram, YouTube, or TikTok.
    """
    out_dir = REELS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "video.%(ext)s")

    # Get title
    title_res = subprocess.run(
        [YT_DLP_PATH, "--get-title", "--no-playlist", "--cookies-from-browser", "chrome", url],
        capture_output=True, text=True, timeout=30,
    )
    title = title_res.stdout.strip() or f"Video {video_id}"

    # Download
    result = subprocess.run(
        [
            YT_DLP_PATH,
            "--no-playlist",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--output", out_template,
            "--merge-output-format", "mp4",
            "--cookies-from-browser", "chrome",
            url,
        ],
        capture_output=True, text=True, timeout=180,
    )

    if result.returncode != 0:
        # Fallback
        subprocess.run(
            [YT_DLP_PATH, "--no-playlist", "--output", out_template, "--cookies-from-browser", "chrome", url],
            capture_output=True, text=True, timeout=180,
        )

    video_files = list(out_dir.glob("video.*"))
    if not video_files:
        raise RuntimeError(f"yt-dlp failed to download video: {result.stderr}")

    return video_files[0], title


def extract_audio(video_path: Path) -> Path:
    """
    Extract audio track as MP3 for Whisper.
    """
    audio_path = video_path.parent / "audio.mp3"
    result = subprocess.run(
        [
            FFMPEG_PATH, "-y", "-i", str(video_path),
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            str(audio_path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
    return audio_path
