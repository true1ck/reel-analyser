"""
Video downloader service — wraps yt-dlp for cross-platform video downloads.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

from backend.config import REELS_DIR


def check_dependencies() -> list[str]:
    """Check for required system tools. Returns list of missing tools."""
    missing = []
    for tool in ["yt-dlp", "ffmpeg"]:
        if not shutil.which(tool):
            missing.append(tool)
    return missing


def download_video(url: str, video_id: str) -> tuple[Path, str]:
    """
    Download a video from Instagram, YouTube, or TikTok.
    
    Returns:
        (video_path, title)
    
    Raises:
        RuntimeError: If download fails.
    """
    out_dir = REELS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Using 'video' as filename to be generic
    out_template = str(out_dir / "video.%(ext)s")

    # Get title
    title_res = subprocess.run(
        ["yt-dlp", "--get-title", "--no-playlist", url],
        capture_output=True, text=True, timeout=30,
    )
    title = title_res.stdout.strip() or f"Video {video_id}"

    # Download
    result = subprocess.run(
        [
            "yt-dlp",
            "--no-playlist",
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--output", out_template,
            "--merge-output-format", "mp4",
            url,
        ],
        capture_output=True, text=True, timeout=180,
    )

    if result.returncode != 0:
        # Fallback to simple download if complex format fails
        subprocess.run(
            ["yt-dlp", "--no-playlist", "--output", out_template, url],
            capture_output=True, text=True, timeout=180,
        )

    video_files = list(out_dir.glob("video.*"))
    if not video_files:
        raise RuntimeError(f"yt-dlp failed to download video: {result.stderr}")

    return video_files[0], title


def extract_audio(video_path: Path) -> Path:
    """
    Extract audio track as WAV for Whisper.
    
    Returns:
        Path to the extracted audio file.
    """
    audio_path = video_path.parent / "audio.wav"
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-ar", "16000", "-ac", "1",
            str(audio_path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
    return audio_path
