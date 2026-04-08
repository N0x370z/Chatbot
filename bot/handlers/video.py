"""Video MP4/MOV."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Video: lógica pendiente (bot/handlers/video.py)."
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("video", cmd_video))
