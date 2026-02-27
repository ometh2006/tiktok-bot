"""
utils/validators.py — Input validation helpers.
Keeps all URL/input sanitation in one place.
"""

import re
from urllib.parse import urlparse

# Patterns that identify TikTok content URLs
TIKTOK_PATTERNS = [
    r"https?://(www\.)?tiktok\.com/@[\w.]+/video/\d+",
    r"https?://vm\.tiktok\.com/[\w]+",
    r"https?://vt\.tiktok\.com/[\w]+",
    r"https?://m\.tiktok\.com/v/\d+",
    r"https?://(www\.)?tiktok\.com/t/[\w]+",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in TIKTOK_PATTERNS]


def is_tiktok_url(text: str) -> bool:
    """Return True if *text* looks like a public TikTok video/post URL."""
    text = text.strip()
    for pattern in _COMPILED:
        if pattern.match(text):
            return True
    # Also accept shortened links that parse to tiktok.com host
    try:
        parsed = urlparse(text)
        return parsed.netloc.lower().endswith("tiktok.com")
    except Exception:
        return False


def extract_url(text: str) -> str | None:
    """
    Pull the first TikTok URL out of an arbitrary message body.
    Returns None if no URL found.
    """
    # Grab anything that looks like a URL
    raw_urls = re.findall(r"https?://\S+", text)
    for url in raw_urls:
        url = url.rstrip(".,;!?)")   # strip trailing punctuation
        if is_tiktok_url(url):
            return url
    return None


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """
    Convert an arbitrary string into a safe filesystem filename.
    Replaces forbidden characters and trims length.
    """
    # Keep only alphanumeric, spaces, hyphens, underscores, dots
    safe = re.sub(r"[^\w\s\-.]", "_", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe[:max_len].strip("_")
    return safe or "tiktok_video"
