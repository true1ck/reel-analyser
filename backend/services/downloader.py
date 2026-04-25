"""
Video downloader service — wraps yt-dlp for cross-platform video downloads.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

from backend.config import REELS_DIR
import os

def get_yt_dlp_base_cmd() -> list[str]:
    """Return base yt-dlp command with cookies if available."""
    base = ["yt-dlp"]
    cookies_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies.txt")
    if os.path.exists(cookies_path):
        base.extend(["--cookies", cookies_path])
    return base


def check_dependencies() -> list[str]:
    """Check for required system tools. Returns list of missing tools."""
    missing = []
    for tool in ["yt-dlp", "ffmpeg"]:
        if not shutil.which(tool):
            missing.append(tool)
    return missing


def fetch_channel_videos(url: str, limit: int = 10) -> list[str]:
    """
    Fetch up to `limit` recent/top video URLs from a channel/profile URL using yt-dlp.
    If it's an Instagram profile, uses the Instagram web_profile_info API directly as a fallback.
    Returns a list of video URLs.
    """
    import json
    import urllib.request
    from urllib.parse import urlparse
    import re
    
    # 1. Instagram Profile Special Handling (bypasses yt-dlp to avoid login blocks)
    if "instagram.com" in url:
        # Extract username from url
        # e.g., https://www.instagram.com/100xengineers?igsh=...
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) == 1 and path_parts[0] not in ('p', 'reel', 'reels', 'tv'):
            username = path_parts[0]
            try:
                api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
                req = urllib.request.Request(api_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'X-IG-App-ID': '936619743392459',
                    'Accept': '*/*'
                })
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    edges = data.get('data', {}).get('user', {}).get('edge_owner_to_timeline_media', {}).get('edges', [])
                    urls = []
                    for edge in edges:
                        if len(urls) >= limit:
                            break
                        node = edge.get('node', {})
                        # Ideally we only want videos, but we can just grab all posts/reels
                        shortcode = node.get('shortcode')
                        if shortcode:
                            urls.append(f"https://www.instagram.com/reel/{shortcode}/")
                    if urls:
                        return urls
            except Exception as e:
                print(f"Instagram direct fetch failed for {username}: {e}")
                # Fall back to yt-dlp just in case

    # 2. Standard yt-dlp fetch for YouTube, TikTok, and other platforms
    cmd = [
        *get_yt_dlp_base_cmd(),
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(limit),
        url
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    
    urls = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            # 'url' might be just the ID or relative path for some extractors.
            # 'webpage_url' is usually the full URL.
            video_url = data.get("webpage_url") or data.get("url")
            if video_url:
                # Add base URL if it's relative
                if video_url.startswith("/"):
                    if "instagram.com" in url:
                        video_url = f"https://www.instagram.com{video_url}"
                    elif "youtube.com" in url:
                        video_url = f"https://www.youtube.com{video_url}"
                    elif "tiktok.com" in url:
                        video_url = f"https://www.tiktok.com{video_url}"
                urls.append(video_url)
        except json.JSONDecodeError:
            continue
            
    return urls


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

    # Fetch metadata with comments
    meta_res = subprocess.run(
        [
            *get_yt_dlp_base_cmd(), "-J", "--no-playlist", 
            "--get-comments", 
            "--extractor-args", "youtube:max-comments=10,1,10;instagram:max-comments=10",
            url
        ],
        capture_output=True, text=True, timeout=60,
    )
    
    metadata = {}
    title = f"Video {video_id}"
    if meta_res.returncode == 0:
        try:
            raw_meta = json.loads(meta_res.stdout)
            title = raw_meta.get("title") or title
            
            # Extract top/pinned comment
            comments = raw_meta.get("comments", [])
            top_comment = None
            if comments:
                # Try to find a pinned one first
                pinned = [c for c in comments if c.get("is_pinned")]
                if pinned:
                    top_comment = pinned[0].get("text")
                else:
                    top_comment = comments[0].get("text")

            metadata = {
                "title": title,
                "uploader": raw_meta.get("uploader"),
                "description": raw_meta.get("description"),
                "view_count": raw_meta.get("view_count"),
                "like_count": raw_meta.get("like_count"),
                "upload_date": raw_meta.get("upload_date"),
                "tags": raw_meta.get("tags", []),
                "top_comment": top_comment
            }
        except json.JSONDecodeError:
            metadata = {"title": title}
    else:
        metadata = {"title": title}

    # Download
    result = subprocess.run(
        [
            *get_yt_dlp_base_cmd(),
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
            [*get_yt_dlp_base_cmd(), "--no-playlist", "--output", out_template, url],
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
