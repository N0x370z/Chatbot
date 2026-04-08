"""Comandos relacionados con libros."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def cmd_libro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Libros: lógica pendiente (bot/handlers/books.py)."
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("libro", cmd_libro))
