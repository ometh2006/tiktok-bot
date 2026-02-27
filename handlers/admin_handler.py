"""
handlers/admin_handler.py — /start, /help, /stats, and admin commands.

Admin commands are silently ignored for non-admins (no error shown),
making it harder for bad actors to probe for admin functions.
"""

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from services.queue_manager import download_queue
from services.rate_limiter import rate_limiter
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ── Helper ────────────────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in Config.ADMIN_IDS


# ── Public commands ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello, *{user.first_name}*\\!\n\n"
        "I'm a *TikTok Downloader Bot*\\. Just send me any public TikTok link "
        "and I'll download the video for you \\— no watermark when possible\\!\n\n"
        "📋 *What I can do:*\n"
        "• 📹 Download videos \\(standard & HD\\)\n"
        "• 🎵 Extract audio as MP3\n"
        "• 🖼 Download slideshow posts\n"
        "• 📌 Show video info & captions\n\n"
        f"⚡ *Free tier limits:*\n"
        f"• {Config.MAX_DOWNLOADS_PER_DAY} downloads per day\n"
        f"• {Config.HD_DOWNLOADS_PER_DAY} HD downloads per day\n\n"
        "Just paste a TikTok link to get started\\!\n"
        "Use /help for more details\\.",
        parse_mode="MarkdownV2",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *How to use this bot:*\n\n"
        "1\\. Copy a TikTok video URL\n"
        "2\\. Paste it here\n"
        "3\\. Choose a format:\n"
        "   • 📹 *Video* — Standard quality MP4\n"
        "   • 🎬 *HD Video* — Best quality \\(limited\\ per\\ day\\)\n"
        "   • 🎵 *Audio* — MP3 extracted from video\n"
        "   • 🖼 *Slideshow* — Photos from carousel posts\n\n"
        "⚠️ *Supported URLs:*\n"
        "• `https://www.tiktok.com/@user/video/…`\n"
        "• `https://vm.tiktok.com/…`\n"
        "• `https://vt.tiktok.com/…`\n\n"
        "🔒 *Only public videos are supported\\.* "
        "Private and removed videos cannot be downloaded\\.\n\n"
        "📊 Use /stats to see your daily usage\\.",
        parse_mode="MarkdownV2",
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = await rate_limiter.get_stats(user.id)

    reset_h = stats["reset_in_seconds"] // 3600
    reset_m = (stats["reset_in_seconds"] % 3600) // 60

    lines = [
        f"📊 *Your stats for today:*",
        f"",
        f"📥 Downloads used: `{stats['downloads_today']} / {Config.MAX_DOWNLOADS_PER_DAY}`",
        f"📥 Downloads left: `{stats['downloads_left']}`",
        f"🎬 HD used: `{stats['hd_today']} / {Config.HD_DOWNLOADS_PER_DAY}`",
        f"🎬 HD left: `{stats['hd_left']}`",
        f"⏰ Resets in: `{reset_h}h {reset_m}m`",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Admin commands ────────────────────────────────────────────────────────────

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /ban <user_id>"""
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    await rate_limiter.ban_user(target_id)
    logger.warning(f"Admin {update.effective_user.id} banned user {target_id}")
    await update.message.reply_text(f"✅ User `{target_id}` has been banned.", parse_mode="Markdown")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /unban <user_id>"""
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    await rate_limiter.unban_user(target_id)
    logger.info(f"Admin {update.effective_user.id} unbanned user {target_id}")
    await update.message.reply_text(f"✅ User `{target_id}` has been unbanned.", parse_mode="Markdown")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Broadcast a message to all users who've interacted with the bot today.
    Usage: /broadcast <message text>
    Note: The in-memory store only knows about users in the current session.
    For production, integrate with a persistent user database.
    """
    if not _is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    text = " ".join(context.args)
    all_stats = await rate_limiter.all_stats()
    user_ids  = [r["user_id"] for r in all_stats if not r.get("is_banned")]

    sent = failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📣 Broadcast complete.\n✅ Sent: {sent} | ❌ Failed: {failed}"
    )

    # ── Admin: queue status ───────────────────────────────────────

async def cmd_queue_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    q = download_queue.status()
    await update.message.reply_text(
        f"📊 *Queue Status*\n"
        f"Active:   `{q['active']}`\n"
        f"Waiting:  `{q['waiting']}`\n"
        f"Total served: `{q['total_served']}`",
        parse_mode="Markdown",
    )
