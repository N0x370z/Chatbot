"""Video: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import stats_from
from bot.handlers.media import enqueue_from_url
from bot.utils.url_args import url_from_message_args


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.effective_message:
        return
    stats_from(context).mark_command("video", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /video <url>\n"
            "Ejemplo: /video https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        return
    await enqueue_from_url(update, context, url=url, kind="video", label="video")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("video", cmd_video))
