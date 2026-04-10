"""Punto de entrada del bot."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from telegram.ext import Application, ContextTypes

from bot.config import get_settings
from bot.handlers import register_handlers
from bot.utils.logger import setup_logging

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(
        "Error no manejado al procesar update=%s",
        update,
        exc_info=context.error,
    )


def main() -> None:

    settings = get_settings()
    setup_logging(settings.log_level)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    application.bot_data["settings"] = settings

    register_handlers(application, admin_user_id=settings.admin_user_id)
    application.add_error_handler(error_handler)

    logger.info("Iniciando bot en modo polling…")
    application.run_polling(allowed_updates=Application.ALL_UPDATES)


if __name__ == "__main__":
    main()
