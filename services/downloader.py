"""
services/downloader.py — Core download logic using yt-dlp.

Responsibilities:
  • Extract video metadata without downloading
  • Download video (standard or HD)
  • Extract audio (MP3)
  • Handle slideshow/photo posts
  • Return structured result objects
"""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yt_dlp

from config import Config
from utils.file_utils import human_size
from utils.logger import setup_logger
from utils.validators import sanitize_filename

logger = setup_logger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class VideoMetadata:
    title: str = "TikTok Video"
    author: str = "Unknown"
    duration: int = 0          # seconds
    description: str = ""
    thumbnail_url: str = ""
    view_count: int = 0
    is_slideshow: bool = False
    webpage_url: str = ""


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    metadata: Optional[VideoMetadata] = None
    is_audio: bool = False
    is_slideshow: bool = False
    photo_paths: list[Path] = field(default_factory=list)
    error: str = ""
    file_size_bytes: int = 0


# ── yt-dlp option factories ───────────────────────────────────────────────────

def _base_opts(output_dir: Path, fmt: str, quiet: bool = True) -> dict:
    """Common yt-dlp options shared by all download types."""
    return {
        "format": fmt,
        "outtmpl": str(output_dir / "%(title).60s.%(ext)s"),
        "quiet": quiet,
        "no_warnings": quiet,
        "noplaylist": True,
        "geo_bypass": True,
        # No-watermark: prefer CDN sources without watermark when available
        "extractor_args": {"tiktok": {"api_hostname": "api22-normal-c-useast1a.tiktokv.com"}},
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        "socket_timeout": Config.DOWNLOAD_TIMEOUT,
        "retries": 3,
        "fragment_retries": 3,
    }


def _audio_opts(output_dir: Path) -> dict:
    opts = _base_opts(output_dir, "bestaudio/best")
    opts["postprocessors"] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]
    opts["outtmpl"] = str(output_dir / "%(title).60s.%(ext)s")
    return opts


# ── Metadata extraction ───────────────────────────────────────────────────────

async def fetch_metadata(url: str) -> VideoMetadata:
    """
    Extract metadata without downloading any media.
    Runs yt-dlp in a thread to avoid blocking the event loop.
    """
    def _extract() -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "geo_bypass": True,
            "extractor_args": {
                "tiktok": {"api_hostname": "api22-normal-c-useast1a.tiktokv.com"}
            },
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await asyncio.to_thread(_extract)

    # Detect slideshow: multiple images, no single video stream
    is_slideshow = (
        info.get("_type") == "playlist"
        or "images" in str(info.get("formats", ""))
        or info.get("ext") in ("none", None)
        and bool(info.get("thumbnails"))
    )

    return VideoMetadata(
        title=info.get("title") or "TikTok Video",
        author=info.get("uploader") or info.get("creator") or "Unknown",
        duration=int(info.get("duration") or 0),
        description=info.get("description") or "",
        thumbnail_url=(info.get("thumbnail") or ""),
        view_count=int(info.get("view_count") or 0),
        is_slideshow=is_slideshow,
        webpage_url=info.get("webpage_url") or url,
    )


# ── Video download ────────────────────────────────────────────────────────────

async def download_video(url: str, output_dir: Path, hd: bool = False) -> DownloadResult:
    """
    Download a TikTok video (MP4).
    hd=True uses the best available quality (counts against HD quota).
    """
    fmt = Config.HD_FORMAT if hd else Config.DEFAULT_FORMAT
    opts = _base_opts(output_dir, fmt)

    def _download() -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_download),
            timeout=Config.DOWNLOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return DownloadResult(success=False, error="timeout")
    except yt_dlp.utils.DownloadError as exc:
        logger.warning(f"yt-dlp error for {url}: {exc}")
        return DownloadResult(success=False, error=_classify_error(str(exc)))

    # Find the output file
    file_path = _find_downloaded_file(output_dir)
    if not file_path:
        return DownloadResult(success=False, error="file_not_found")

    size = file_path.stat().st_size
    if size > Config.MAX_FILE_SIZE_MB * 1024 * 1024:
        file_path.unlink(missing_ok=True)
        return DownloadResult(
            success=False,
            error=f"too_large:{human_size(size)}",
        )

    meta = VideoMetadata(
        title=info.get("title") or "TikTok Video",
        author=info.get("uploader") or "Unknown",
        duration=int(info.get("duration") or 0),
        description=info.get("description") or "",
        thumbnail_url=info.get("thumbnail") or "",
        view_count=int(info.get("view_count") or 0),
        webpage_url=info.get("webpage_url") or url,
    )

    return DownloadResult(
        success=True,
        file_path=file_path,
        metadata=meta,
        file_size_bytes=size,
    )


# ── Audio extraction ──────────────────────────────────────────────────────────

async def download_audio(url: str, output_dir: Path) -> DownloadResult:
    """Extract audio as MP3 from a TikTok video."""
    opts = _audio_opts(output_dir)

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_download),
            timeout=Config.DOWNLOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return DownloadResult(success=False, error="timeout", is_audio=True)
    except yt_dlp.utils.DownloadError as exc:
        return DownloadResult(
            success=False,
            error=_classify_error(str(exc)),
            is_audio=True,
        )

    file_path = _find_downloaded_file(output_dir, ext=".mp3")
    if not file_path:
        return DownloadResult(success=False, error="file_not_found", is_audio=True)

    meta = VideoMetadata(
        title=info.get("title") or "TikTok Audio",
        author=info.get("uploader") or "Unknown",
        duration=int(info.get("duration") or 0),
    )

    return DownloadResult(
        success=True,
        file_path=file_path,
        metadata=meta,
        is_audio=True,
        file_size_bytes=file_path.stat().st_size,
    )


# ── Slideshow / Photo post ────────────────────────────────────────────────────

async def download_slideshow(url: str, output_dir: Path) -> DownloadResult:
    """
    Download a TikTok slideshow (photo carousel).
    Falls back to downloading a video of the slideshow if individual
    frames aren't available.
    """
    opts = _base_opts(output_dir, "best")
    opts["outtmpl"] = str(output_dir / "slide_%(autonumber)s.%(ext)s")

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_download),
            timeout=Config.DOWNLOAD_TIMEOUT,
        )
    except Exception as exc:
        logger.warning(f"Slideshow download failed: {exc}")
        return DownloadResult(success=False, error="slideshow_failed", is_slideshow=True)

    photos = sorted(output_dir.glob("slide_*"))
    if not photos:
        # Fall back: might have saved as a single video
        file_path = _find_downloaded_file(output_dir)
        if file_path:
            return DownloadResult(
                success=True,
                file_path=file_path,
                is_slideshow=False,
                file_size_bytes=file_path.stat().st_size,
            )
        return DownloadResult(success=False, error="slideshow_failed", is_slideshow=True)

    meta = VideoMetadata(
        title=info.get("title") or "TikTok Slideshow",
        author=info.get("uploader") or "Unknown",
        is_slideshow=True,
    )

    return DownloadResult(
        success=True,
        metadata=meta,
        is_slideshow=True,
        photo_paths=photos,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_downloaded_file(directory: Path, ext: str | None = None) -> Path | None:
    """Return the first (or largest) file in *directory*, optionally filtered by ext."""
    candidates = [
        f for f in directory.iterdir()
        if f.is_file() and (ext is None or f.suffix.lower() == ext)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_size)


def _classify_error(message: str) -> str:
    """Map yt-dlp error messages to short error codes."""
    msg = message.lower()
    if "private" in msg or "login" in msg:
        return "private"
    if "not available" in msg or "removed" in msg or "deleted" in msg:
        return "removed"
    if "geo" in msg or "region" in msg or "country" in msg:
        return "geo_blocked"
    if "rate" in msg or "too many" in msg or "429" in msg:
        return "rate_limited"
    if "network" in msg or "connection" in msg or "timeout" in msg:
        return "network_error"
    return "download_failed"
