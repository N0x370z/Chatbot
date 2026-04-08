"""Registro de todos los handlers de comandos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.handlers import admin, audio, books, video


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "TelegramMediaBot — esqueleto listo. Implementa la lógica en bot/handlers/ "
        "y bot/utils/."
    )


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Comandos (esqueleto):\n"
        "/libro — búsqueda de libros\n"
        "/audio — audio (MP3/M4A)\n"
        "/video — video (MP4)\n"
        "/apple — formatos Apple (M4A/AAC/M4B)\n"
        "/ayuda — esta ayuda\n"
        "/stats — estadísticas (solo admin)\n"
    )
    await update.effective_message.reply_text(text)


def register_handlers(application: Application, admin_user_id: int) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    books.register(application)
    audio.register(application)
    video.register(application)
    admin.register(application, admin_user_id=admin_user_id)
