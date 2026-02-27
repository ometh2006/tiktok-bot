"""
handlers/callback_handler.py — Handles inline keyboard button presses.

Looks up the full URL from context.bot_data["url_store"] using the short
key stored in callback_data, then executes the download.
"""

import asyncio

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import Config
from services.downloader import (
    download_video,
    download_audio,
    download_slideshow,
    DownloadResult,
)
from services.queue_manager import download_queue
from services.rate_limiter import rate_limiter
from utils.file_utils import temp_directory, human_size
from utils.logger import setup_logger

logger = setup_logger(__name__)

MSG_DOWNLOADING = "⬇️ Downloading… please wait."
MSG_SENDING     = "📤 Sending to you…"

ERROR_MESSAGES = {
    "private":          "🔒 This video is *private* or requires login. Only public videos are supported.",
    "removed":          "🗑 This video has been *removed* or is no longer available.",
    "geo_blocked":      "🌍 This video is *geo-restricted* and not available in the bot's region.",
    "rate_limited":     "🚦 TikTok is *rate-limiting* requests. Please try again in a few minutes.",
    "network_error":    "🌐 A *network error* occurred. Please try again.",
    "timeout":          "⏱ The download *timed out*. The video may be too large or the server is slow.",
    "file_not_found":   "❓ The file couldn't be located after download. Please try again.",
    "slideshow_failed": "🖼 Couldn't download the slideshow. Try the *Video* option instead.",
    "download_failed":  "❌ Download failed. Please check the link and try again.",
}


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user  = query.from_user

    await query.answer()

    data = query.data or ""
    if not data.startswith("dl:"):
        return

    parts = data.split(":", 2)
    if len(parts) != 3:
        return

    _, dl_type, url_key = parts

    # Resolve the short key back to the full URL
    url_store = context.bot_data.get("url_store", {})
    url = url_store.get(url_key)
    if not url:
        await query.edit_message_text("❌ Session expired. Please send the TikTok link again.")
        return

    is_hd = dl_type == "hd"

    # Re-check ban and rate limit
    if await rate_limiter.is_banned(user.id):
        await query.edit_message_text("🚫 You have been banned.")
        return

    allowed, reason = await rate_limiter.can_download(user.id)
    if not allowed:
        await query.edit_message_text("⏳ Daily limit reached. Try again later.")
        return

    if is_hd and not await rate_limiter.can_use_hd(user.id):
        await query.edit_message_text(
            f"🎬 You've used all *{Config.HD_DOWNLOADS_PER_DAY} HD downloads* for today.\n"
            f"Use the standard 📹 Video button instead.",
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(MSG_DOWNLOADING)

    try:
        await download_queue.run(
            _execute_download(query, user.id, url, dl_type)
        )
    except asyncio.QueueFull:
        await query.edit_message_text(
            "😔 The bot is very busy right now. Please try again in a moment."
        )


async def _execute_download(query, user_id: int, url: str, dl_type: str) -> None:
    is_hd    = dl_type == "hd"
    is_audio = dl_type == "audio"
    is_slide = dl_type == "slide"

    async with temp_directory() as tmpdir:
        # Download
        if is_audio:
            result: DownloadResult = await download_audio(url, tmpdir)
        elif is_slide:
            result = await download_slideshow(url, tmpdir)
        else:
            result = await download_video(url, tmpdir, hd=is_hd)

        if not result.success:
            err_code = result.error.split(":")[0]
            err_msg = ERROR_MESSAGES.get(err_code, ERROR_MESSAGES["download_failed"])
            if result.error.startswith("too_large:"):
                size_str = result.error.split(":", 1)[1]
                err_msg = (
                    f"📦 File is *too large* to send via Telegram ({size_str}).\n"
                    f"Telegram bots are limited to {Config.MAX_FILE_SIZE_MB} MB."
                )
            await query.edit_message_text(err_msg, parse_mode="Markdown")
            return

        await query.edit_message_text(MSG_SENDING)
        meta = result.metadata
        caption = ""
        if meta:
            caption = (
                f"{'🎵' if is_audio else '📹'} *{meta.title[:80]}*\n"
                f"👤 @{meta.author}"
            )
            if meta.description:
                caption += f"\n\n_{meta.description[:200]}_"

        chat_id = query.message.chat_id
        bot     = query.get_bot()

        try:
            if result.is_slideshow and result.photo_paths:
                from telegram import InputMediaPhoto
                media = [
                    InputMediaPhoto(
                        media=open(str(p), "rb"),
                        caption=(caption if i == 0 else ""),
                        parse_mode="Markdown",
                    )
                    for i, p in enumerate(result.photo_paths[:10])
                ]
                await bot.send_media_group(chat_id=chat_id, media=media)

            elif is_audio and result.file_path:
                with open(result.file_path, "rb") as f:
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        caption=caption,
                        parse_mode="Markdown",
                        title=meta.title if meta else "TikTok Audio",
                        performer=meta.author if meta else "TikTok",
                    )

            elif result.file_path:
                with open(result.file_path, "rb") as f:
                    size_str = human_size(result.file_size_bytes)
                    full_caption = caption + f"\n\n📦 Size: `{size_str}`"
                    await bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=full_caption,
                        parse_mode="Markdown",
                        supports_streaming=True,
                    )

        except TelegramError as exc:
            logger.error(f"Failed to send file to {user_id}: {exc}")
            await query.edit_message_text(
                f"❌ Couldn't send the file: {exc}\n\nPlease try again."
            )
            return

        # Record download
        await rate_limiter.record_download(user_id, is_hd=is_hd)

        # Clean up menu message
        try:
            await query.delete_message()
        except TelegramError:
            pass

        logger.info(f"✅ Delivered {dl_type} to user {user_id} ({human_size(result.file_size_bytes)})")
