"""
╔══════════════════════════════════════════════════════════════════╗
║         TikTok Downloader Bot — Production-Ready                ║
║         Author: Your Name | License: MIT                        ║
╚══════════════════════════════════════════════════════════════════╝
Entry point. Registers all handlers and starts the bot in
polling or webhook mode based on config.
"""

import asyncio
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import Config
from handlers.message_handler import handle_url, handle_unknown
from handlers.callback_handler import handle_callback
from handlers.admin_handler import (
    cmd_start,
    cmd_help,
    cmd_stats,
    cmd_broadcast,
    cmd_ban,
    cmd_unban,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def post_init(application: Application) -> None:
    """Set bot commands shown in Telegram menu."""
    commands = [
        BotCommand("start", "Welcome message & instructions"),
        BotCommand("help", "How to use the bot"),
        BotCommand("stats", "Your personal usage stats"),
        BotCommand("cancel", "Cancel current download"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered.")


def build_application() -> Application:
    """Build and configure the Telegram Application."""
    app = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .concurrent_updates(True)          # Handle updates concurrently
        .post_init(post_init)
        .build()
    )

    # ── Command handlers ─────────────────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))   # admin only
    app.add_handler(CommandHandler("ban", cmd_ban))               # admin only
    app.add_handler(CommandHandler("unban", cmd_unban))           # admin only

    # ── URL messages ──────────────────────────────────────────────
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
    )

    # ── Inline button callbacks ───────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Fallback ──────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.ALL, handle_unknown))

    return app


def main() -> None:
    logger.info("Starting TikTok Downloader Bot…")

    # Start HTTP health server so Koyeb/Render health checks pass
    from keep_alive import keep_alive
    keep_alive(port=8000)

    app = build_application()

    if Config.WEBHOOK_URL:
        # ── Webhook mode ──────────────────────────────────────────
        logger.info(f"Webhook mode → {Config.WEBHOOK_URL}")
        app.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            webhook_url=Config.WEBHOOK_URL,
            secret_token=Config.WEBHOOK_SECRET,
        )
    else:
        # ── Polling mode (default, no SSL needed) ─────────────────
        logger.info("Polling mode started.")
        app.run_polling(
            poll_interval=1,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )


if __name__ == "__main__":
    main()
