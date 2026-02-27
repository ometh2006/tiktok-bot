"""
utils/file_utils.py — Temporary file management.
Creates isolated per-request temp directories and guarantees cleanup
even if an exception occurs mid-download.
"""

import asyncio
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


def ensure_temp_dir() -> Path:
    """Create the global temp directory if it doesn't exist."""
    path = Path(Config.TEMP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_request_dir() -> Path:
    """Create a unique subdirectory for a single download request."""
    base = ensure_temp_dir()
    req_dir = base / str(uuid.uuid4())
    req_dir.mkdir(parents=True, exist_ok=True)
    return req_dir


def remove_dir(path: Path) -> None:
    """Silently remove a directory tree."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception as exc:
        logger.warning(f"Could not remove temp dir {path}: {exc}")


@asynccontextmanager
async def temp_directory():
    """
    Async context manager that yields a fresh temp directory path
    and deletes it automatically when the block exits.

    Usage:
        async with temp_directory() as tmpdir:
            # tmpdir is a Path object; put files there
            ...
        # directory is gone here
    """
    req_dir = await asyncio.to_thread(make_request_dir)
    try:
        yield req_dir
    finally:
        await asyncio.to_thread(remove_dir, req_dir)


def human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
