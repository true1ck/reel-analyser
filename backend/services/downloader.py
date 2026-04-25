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


def download_video(url: str, video_id: str) -> tuple[Path, dict]:
    """
    Download a video from Instagram, YouTube, or TikTok and fetch metadata.
    
    Returns:
        (video_path, metadata_dict)
    
    Raises:
        RuntimeError: If download fails.
    """
    import json
    out_dir = REELS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "video.%(ext)s")

    # Fetch metadata
    meta_res = subprocess.run(
        ["yt-dlp", "-J", "--no-playlist", url],
        capture_output=True, text=True, timeout=30,
    )
    
    metadata = {}
    title = f"Video {video_id}"
    if meta_res.returncode == 0:
        try:
            raw_meta = json.loads(meta_res.stdout)
            title = raw_meta.get("title") or title
            metadata = {
                "title": title,
                "uploader": raw_meta.get("uploader"),
                "description": raw_meta.get("description"),
                "view_count": raw_meta.get("view_count"),
                "like_count": raw_meta.get("like_count"),
                "upload_date": raw_meta.get("upload_date"),
                "tags": raw_meta.get("tags", []),
            }
        except json.JSONDecodeError:
            metadata = {"title": title}
    else:
        metadata = {"title": title}

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

    return video_files[0], metadata


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
