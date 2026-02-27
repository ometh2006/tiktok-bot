"""
services/rate_limiter.py — Per-user rate limiting.

Tracks:
  • Total daily downloads  (default 5/day)
  • HD downloads           (default 2/day)
  • Banned users

Uses an in-memory store (dict).  On free-tier hosts that restart
frequently this resets daily automatically — which is fine because
the window is 24 hours.

For persistence across restarts, replace the dict with SQLite or
a Redis call (both available free on Railway / Upstash).
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict

from config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class UserRecord:
    downloads_today: int = 0
    hd_today: int = 0
    window_start: float = field(default_factory=time.time)
    is_banned: bool = False


class RateLimiter:
    """Thread-safe async rate limiter backed by an in-memory dict."""

    def __init__(self) -> None:
        self._records: Dict[int, UserRecord] = {}
        self._lock = asyncio.Lock()
        # Seed banned users from config
        for uid in Config.BANNED_USERS:
            self._records[uid] = UserRecord(is_banned=True)

    # ── Internal helpers ──────────────────────────────────────────

    def _get_or_create(self, user_id: int) -> UserRecord:
        rec = self._records.setdefault(user_id, UserRecord())
        # Reset counters if 24-hour window has passed
        if time.time() - rec.window_start >= Config.RATE_WINDOW_SECONDS:
            rec.downloads_today = 0
            rec.hd_today = 0
            rec.window_start = time.time()
        return rec

    # ── Public API ────────────────────────────────────────────────

    async def is_banned(self, user_id: int) -> bool:
        async with self._lock:
            rec = self._records.get(user_id)
            return rec.is_banned if rec else False

    async def can_download(self, user_id: int) -> tuple[bool, str]:
        """
        Returns (allowed, reason).
        reason is empty string when allowed=True.
        """
        async with self._lock:
            rec = self._get_or_create(user_id)
            if rec.is_banned:
                return False, "banned"
            if rec.downloads_today >= Config.MAX_DOWNLOADS_PER_DAY:
                remaining = Config.RATE_WINDOW_SECONDS - (time.time() - rec.window_start)
                hours = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                return False, f"daily_limit:{hours}h{mins}m"
            return True, ""

    async def can_use_hd(self, user_id: int) -> bool:
        async with self._lock:
            rec = self._get_or_create(user_id)
            return rec.hd_today < Config.HD_DOWNLOADS_PER_DAY

    async def record_download(self, user_id: int, is_hd: bool = False) -> None:
        async with self._lock:
            rec = self._get_or_create(user_id)
            rec.downloads_today += 1
            if is_hd:
                rec.hd_today += 1
            logger.info(
                f"User {user_id} | daily={rec.downloads_today} hd={rec.hd_today}"
            )

    async def get_stats(self, user_id: int) -> dict:
        async with self._lock:
            rec = self._get_or_create(user_id)
            remaining = max(
                0,
                Config.RATE_WINDOW_SECONDS - (time.time() - rec.window_start),
            )
            return {
                "downloads_today": rec.downloads_today,
                "downloads_left": max(0, Config.MAX_DOWNLOADS_PER_DAY - rec.downloads_today),
                "hd_today": rec.hd_today,
                "hd_left": max(0, Config.HD_DOWNLOADS_PER_DAY - rec.hd_today),
                "reset_in_seconds": int(remaining),
                "is_banned": rec.is_banned,
            }

    async def ban_user(self, user_id: int) -> None:
        async with self._lock:
            rec = self._get_or_create(user_id)
            rec.is_banned = True
            logger.warning(f"User {user_id} banned.")

    async def unban_user(self, user_id: int) -> None:
        async with self._lock:
            rec = self._get_or_create(user_id)
            rec.is_banned = False
            logger.info(f"User {user_id} unbanned.")

    async def all_stats(self) -> list[dict]:
        """Admin: return stats for every tracked user."""
        async with self._lock:
            result = []
            for uid, rec in self._records.items():
                result.append({"user_id": uid, **rec.__dict__})
            return result


# Singleton — import this everywhere
rate_limiter = RateLimiter()
