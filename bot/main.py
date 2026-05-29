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
from telegram.ext import Application, ApplicationHandlerStop, ContextTypes, TypeHandler

from bot.config import Settings, get_settings
from bot.db import Database
from bot.download_queue import DownloadQueue
from bot.handlers import register_handlers
from bot.state import BotStats, RateLimiter
from bot.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    headers = {"User-Agent": "TelegramMediaBot/1.0"}
    if settings.books_api_key:
        key_prefix = settings.books_api_key_prefix
        key_value = f"{key_prefix} {settings.books_api_key}".strip() if key_prefix else settings.books_api_key
        headers[settings.books_api_key_header] = key_value
    timeout = aiohttp.ClientTimeout(total=settings.books_api_timeout_sec)
    connector = aiohttp.TCPConnector(ssl=settings.ssl_verify)
    application.bot_data["http_session"] = aiohttp.ClientSession(
        headers=headers,
        timeout=timeout,
        connector=connector,
    )
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Mostrar el menú principal"),
        BotCommand("ayuda", "Ver todos los comandos"),
        BotCommand("libro", "Buscar un libro por título o autor"),
        BotCommand("fuente", "Cambiar la fuente de búsqueda de libros"),
        BotCommand("convertir", "Convertir PDF/EPUB subido a otro formato"),
        BotCommand("audio", "Descargar audio desde una URL"),
        BotCommand("video", "Descargar video desde una URL"),
        BotCommand("formato_audio", "Cambiar formato de audio (MP3/M4A/OPUS/FLAC)"),
        BotCommand("jobs", "Ver el estado de tus descargas"),
        BotCommand("cancelar", "Cancelar la última descarga pendiente"),
        BotCommand("estado", "Ver tus preferencias actuales"),
        BotCommand("version", "Mostrar la versión del bot"),
    ]
    await application.bot.set_my_commands(commands)

async def post_shutdown(application: Application) -> None:
    session: aiohttp.ClientSession | None = application.bot_data.get("http_session")
    if session is not None and not session.closed:
        await session.close()

    queue = application.bot_data.get("download_queue")
    if queue is not None:
        queue.shutdown()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(
        "Error no manejado al procesar update=%s",
        update,
        exc_info=context.error,
    )
    # Notify user if possible, without leaking tracebacks
    try:
        effective_message = getattr(update, "effective_message", None)
        if effective_message is not None:
            await effective_message.reply_text(
                "Algo falló procesando tu solicitud. Revisa /jobs o intenta de nuevo."
            )
    except Exception:
        pass


async def check_allowed_user(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TypeHandler in group=-2: reject users not in the allow-list."""
    settings: Settings = context.bot_data["settings"]
    allowed = settings.allowed_user_ids
    if not allowed:
        return  # no restriction
    user = getattr(update, "effective_user", None)
    if user is None:
        return
    if user.id == settings.admin_user_id or user.id in allowed:
        return
    # Reject and stop processing
    logger.info("Update de usuario no autorizado: %s", user.id)
    try:
        effective_message = getattr(update, "effective_message", None)
        if effective_message is not None:
            await effective_message.reply_text("No estás autorizado para usar este bot.")
    except Exception:
        pass
    raise ApplicationHandlerStop()


async def on_any_update(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user = getattr(update, "effective_user", None)
        chat = getattr(update, "effective_chat", None)
        message = getattr(update, "effective_message", None)
        logger.info(
            "Update recibido: user_id=%s chat_id=%s has_text=%s",
            user.id if user else None,
            chat.id if chat else None,
            message is not None and bool(message.text),
        )
        if user:
            from bot.deps import db_from
            db = db_from(context)
            await db.add_user(user.id)
            if await db.is_banned(user.id):
                logger.info("Ignorando update de usuario baneado: %s", user.id)
                raise ApplicationHandlerStop()

    except ApplicationHandlerStop:
        raise
    except Exception:
        logger.exception("Error inesperado en on_any_update")
        raise


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

    db_path = settings.download_path / "bot.sqlite"
    application.bot_data["db"] = Database(db_path)

    register_handlers(application, admin_user_id=settings.admin_user_id)
    application.add_handler(TypeHandler(object, check_allowed_user), group=-2)
    application.add_handler(TypeHandler(object, on_any_update), group=-1)
    application.add_error_handler(error_handler)

    logger.info("Iniciando bot en modo polling…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
