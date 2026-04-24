"""Punto de entrada del bot."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import aiohttp
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

from bot.config import Settings, get_settings
from bot.download_queue import DownloadQueue
from bot.handlers import register_handlers
from bot.state import BotStats, RateLimiter
from bot.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    headers = {"User-Agent": "TelegramMediaBot/1.0"}
    if settings.books_api_key:
        headers["Authorization"] = f"Bearer {settings.books_api_key}"
    timeout = aiohttp.ClientTimeout(total=settings.books_api_timeout_sec)
    application.bot_data["http_session"] = aiohttp.ClientSession(
        headers=headers,
        timeout=timeout,
    )


async def post_shutdown(application: Application) -> None:
    session: aiohttp.ClientSession | None = application.bot_data.get("http_session")
    if session is not None and not session.closed:
        await session.close()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(
        "Error no manejado al procesar update=%s",
        update,
        exc_info=context.error,
    )


async def on_any_update(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = getattr(update, "effective_user", None)
    chat = getattr(update, "effective_chat", None)
    message = getattr(update, "effective_message", None)
    logger.info(
        "Update recibido: user_id=%s chat_id=%s text=%s",
        user.id if user else None,
        chat.id if chat else None,
        message.text if message else None,
    )


def main() -> None:

    settings = get_settings()
    setup_logging(settings.log_level)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    stats = BotStats()
    application.bot_data["settings"] = settings
    application.bot_data["stats"] = stats
    application.bot_data["limiter"] = RateLimiter(
        window_seconds=settings.rate_limit_window_sec,
        max_requests=settings.rate_limit_max_requests,
    )
    application.bot_data["download_queue"] = DownloadQueue(
        settings=settings,
        stats=stats,
    )

    register_handlers(application, admin_user_id=settings.admin_user_id)
    application.add_handler(TypeHandler(object, on_any_update), group=-1)
    application.add_error_handler(error_handler)

    logger.info("Iniciando bot en modo polling…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
