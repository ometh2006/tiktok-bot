"""
services/queue_manager.py — Async download queue.

Limits the number of simultaneous yt-dlp processes so the bot
doesn't exhaust RAM on cheap hosting. Excess requests wait in
an asyncio.Queue until a slot opens.
"""

import asyncio
from utils.logger import setup_logger
from config import Config

logger = setup_logger(__name__)


class DownloadQueue:
    """
    Wraps asyncio.Semaphore to cap concurrent downloads and
    provides a queue-depth counter for monitoring.
    """

    def __init__(self, max_concurrent: int = Config.MAX_CONCURRENT_DOWNLOADS) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._waiting = 0
        self._active = 0
        self._total_served = 0

    @property
    def waiting(self) -> int:
        return self._waiting

    @property
    def active(self) -> int:
        return self._active

    @property
    def total_served(self) -> int:
        return self._total_served

    async def run(self, coro):
        """
        Acquire a slot, run *coro*, then release.
        Raises asyncio.QueueFull if the queue is already saturated.
        """
        if self._waiting >= Config.MAX_QUEUE_SIZE:
            raise asyncio.QueueFull(
                f"Queue is full ({Config.MAX_QUEUE_SIZE} waiting). Try again later."
            )

        self._waiting += 1
        logger.debug(f"Queue: waiting={self._waiting} active={self._active}")

        async with self._semaphore:
            self._waiting -= 1
            self._active += 1
            try:
                result = await coro
                self._total_served += 1
                return result
            finally:
                self._active -= 1
                logger.debug(f"Queue: slot freed. active={self._active}")

    def status(self) -> dict:
        return {
            "active": self._active,
            "waiting": self._waiting,
            "total_served": self._total_served,
        }


# Singleton
download_queue = DownloadQueue()
