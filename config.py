"""
config.py — Central configuration loader.
All tuneable parameters live here; read from environment variables
so the bot works with .env files, Railway/Render secrets, or Replit secrets.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # loads .env file if present


class Config:
    # ── Core ──────────────────────────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]

    # ── Webhook (leave WEBHOOK_URL empty to use polling) ──────────
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "supersecret")
    PORT: int = int(os.getenv("PORT", "8443"))

    # ── Rate limiting ─────────────────────────────────────────────
    MAX_DOWNLOADS_PER_DAY: int = int(os.getenv("MAX_DOWNLOADS_PER_DAY", "5"))
    HD_DOWNLOADS_PER_DAY: int = int(os.getenv("HD_DOWNLOADS_PER_DAY", "2"))
    RATE_WINDOW_SECONDS: int = 86_400          # 24-hour window

    # ── Queue ─────────────────────────────────────────────────────
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT", "4"))
    MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "20"))
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))   # seconds

    # ── File limits ───────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))    # Telegram limit
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/tiktok_bot")

    # ── Download quality ──────────────────────────────────────────
    DEFAULT_FORMAT: str = "best[ext=mp4]/best"      # yt-dlp format string
    HD_FORMAT: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")

    # ── Banned users (runtime, loaded from env as comma-sep IDs) ──
    BANNED_USERS: set[int] = {
        int(x) for x in os.getenv("BANNED_USERS", "").split(",") if x.strip()
    }

    @classmethod
    def validate(cls) -> None:
        """Raise if critical config is missing."""
        if not cls.BOT_TOKEN:
            raise EnvironmentError(
                "BOT_TOKEN is not set. Add it to your .env file or environment variables."
            )
        if cls.MAX_FILE_SIZE_MB > 50:
            raise ValueError("Telegram bots can only send files up to 50 MB.")
