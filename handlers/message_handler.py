"""
handlers/message_handler.py — Handles incoming text messages.

Flow:
  1. Extract TikTok URL from message
  2. Check rate limits and ban status
  3. Fetch metadata (fast, no download yet)
  4. Store URL in bot_data with a short UUID key
  5. Show inline buttons using the short key (Telegram limits callback_data to 64 bytes)
"""

import asyncio
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import Config
from services.downloader import fetch_metadata
from services.rate_limiter import rate_limiter
from utils.logger import setup_logger
from utils.validators import extract_url, is_tiktok_url

logger = setup_logger(__name__)

MSG_NOT_TIKTOK = (
    "🔗 Please send a valid *TikTok* video link.\n\n"
    "_Example:_ `https://www.tiktok.com/@user/video/123`\n\n"
    "Use /help for instructions."
)
MSG_BANNED = "🚫 You have been banned from using this bot."
MSG_RATE_LIMIT = (
    "⏳ You've reached your daily limit of *{limit} downloads*.\n"
    "⏰ Resets in *{reset}*.\n\n"
    "_Tip: HD downloads also count toward your limit._"
)
MSG_FETCHING = "🔍 Fetching video info…"
MSG_META_ERROR = (
    "❌ Couldn't retrieve video info.\n\n"
    "Possible reasons:\n"
    "• Video is private or deleted\n"
    "• Region-restricted content\n"
    "• Invalid URL\n\n"
    "Please check the link and try again."
)


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for all non-command text messages."""
    user = update.effective_user
    message = update.message
    text = message.text or ""

    # 1. Extract URL
    url = extract_url(text)
    if not url:
        if is_tiktok_url(text.strip()):
            url = text.strip()
        else:
            await message.reply_text(MSG_NOT_TIKTOK, parse_mode="Markdown")
            return

    logger.info(f"User {user.id} (@{user.username}) → {url}")

    # 2. Ban check
    if await rate_limiter.is_banned(user.id):
        await message.reply_text(MSG_BANNED)
        return

    # 3. Daily quota check
    allowed, reason = await rate_limiter.can_download(user.id)
    if not allowed:
        if reason.startswith("daily_limit:"):
            reset_str = reason.split(":", 1)[1]
            await message.reply_text(
                MSG_RATE_LIMIT.format(
                    limit=Config.MAX_DOWNLOADS_PER_DAY,
                    reset=reset_str,
                ),
                parse_mode="Markdown",
            )
        return

    # 4. Fetch metadata
    status_msg = await message.reply_text(MSG_FETCHING)
    try:
        metadata = await asyncio.wait_for(fetch_metadata(url), timeout=30)
    except Exception as exc:
        logger.warning(f"Metadata fetch failed for {url}: {exc}")
        await status_msg.edit_text(MSG_META_ERROR)
        return

    # 5. Store URL with a short key
    # Telegram callback_data is limited to 64 bytes, so we store the URL
    # in bot_data and pass only a short 8-char key in the button.
    url_key = str(uuid.uuid4())[:8]
    if "url_store" not in context.bot_data:
        context.bot_data["url_store"] = {}
    context.bot_data["url_store"][url_key] = url

    # 6. Build inline keyboard — "dl:<type>:<key>" is always under 64 bytes
    hd_available = await rate_limiter.can_use_hd(user.id)
    hd_label = (
        "🎬 HD Video"
        if hd_available
        else f"🎬 HD (0/{Config.HD_DOWNLOADS_PER_DAY} left)"
    )

    keyboard = [
        [
            InlineKeyboardButton("📹 Video", callback_data=f"dl:video:{url_key}"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl:audio:{url_key}"),
        ],
        [
            InlineKeyboardButton(hd_label, callback_data=f"dl:hd:{url_key}"),
        ],
    ]
    if metadata.is_slideshow:
        keyboard.insert(
            0,
            [InlineKeyboardButton("🖼 Slideshow Photos", callback_data=f"dl:slide:{url_key}")],
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    # 7. Show metadata summary
    duration_str = _format_duration(metadata.duration)
    caption = (
        f"📌 *{_esc(metadata.title[:80])}*\n"
        f"👤 `@{_esc(metadata.author)}`\n"
        f"⏱ Duration: `{duration_str}`\n\n"
        f"Choose a format below 👇"
    )
    if metadata.is_slideshow:
        caption = "🖼 *Slideshow detected*\n\n" + caption

    await status_msg.edit_text(
        caption,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for unsupported message types."""
    if update.message:
        await update.message.reply_text(
            "👋 Send me a TikTok link and I'll download it for you!\n"
            "Use /help for instructions.",
        )


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Unknown"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _esc(text: str) -> str:
    """Escape Markdown special characters."""
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text
