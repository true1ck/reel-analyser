"""
URL parsing and validation utilities for Instagram Reel, YouTube Shorts, and TikTok URLs.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse, parse_qs


# Patterns that match various video URLs
VIDEO_PATTERNS = {
    "instagram": [
        # https://www.instagram.com/reel/ABC123/
        re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/reel/([A-Za-z0-9_-]+)"),
        # https://www.instagram.com/p/ABC123/
        re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/p/([A-Za-z0-9_-]+)"),
    ],
    "youtube": [
        # https://www.youtube.com/shorts/ABC123
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]+)"),
        # https://youtu.be/ABC123
        re.compile(r"(?:https?://)?youtu\.be/([A-Za-z0-9_-]+)"),
        # https://www.youtube.com/watch?v=ABC123
        re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]+)"),
    ],
    "tiktok": [
        # https://www.tiktok.com/@user/video/123456789
        re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)"),
        # https://vm.tiktok.com/ABC123
        re.compile(r"(?:https?://)?vm\.tiktok\.com/([A-Za-z0-9_-]+)"),
    ]
}

# Bare ID pattern (fallback for Instagram style IDs)
BARE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,15}$")


def extract_video_info(url_or_id: str) -> tuple[str, str, str] | tuple[None, None, None]:
    """
    Extract (platform, video_id, canonical_url) from a URL or bare ID.
    Returns (None, None, None) if the input doesn't match any known format.
    """
    url_or_id = url_or_id.strip()
    if not url_or_id:
        return None, None, None

    # Try platform patterns
    for platform, patterns in VIDEO_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(url_or_id)
            if match:
                video_id = match.group(1)
                if platform == "instagram":
                    url = f"https://www.instagram.com/reel/{video_id}/"
                elif platform == "youtube":
                    url = f"https://www.youtube.com/shorts/{video_id}"
                elif platform == "tiktok":
                    url = f"https://www.tiktok.com/video/{video_id}"
                return platform, video_id, url

    # Try bare ID (assume Instagram if no platform match)
    if BARE_ID_PATTERN.match(url_or_id):
        return "instagram", url_or_id, f"https://www.instagram.com/reel/{url_or_id}/"

    return None, None, None


def parse_batch_input(raw_text: str) -> list[dict]:
    """
    Parse a block of text containing one or more URLs/IDs.
    Supports newline, comma, and space-separated values.

    Returns a list of dicts:
        [{"original": "...", "url": "...", "reel_id": "...", "platform": "..."}, ...]
    """
    # Split on newlines, commas, or multiple spaces
    candidates = re.split(r"[\n,]+", raw_text)
    results = []
    seen_ids = set()

    for raw in candidates:
        raw = raw.strip()
        if not raw:
            continue

        platform, video_id, url = extract_video_info(raw)
        if video_id and video_id not in seen_ids:
            seen_ids.add(video_id)
            results.append({
                "original": raw,
                "url": url,
                "reel_id": video_id,  # Keeping 'reel_id' for DB compatibility
                "platform": platform
            })
        elif video_id is None:
            results.append({
                "original": raw,
                "url": None,
                "reel_id": None,
                "platform": None
            })
        # Skip duplicates silently

    return results
