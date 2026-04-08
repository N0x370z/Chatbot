"""Audio MP3/M4A/AAC y variantes Apple."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Audio: lógica pendiente (bot/handlers/audio.py)."
    )


async def cmd_apple(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Apple / iPod: lógica pendiente (bot/handlers/audio.py — /apple)."
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("audio", cmd_audio))
    application.add_handler(CommandHandler("apple", cmd_apple))
