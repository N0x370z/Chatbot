"""Video: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import limiter_from, queue_from, stats_from
from bot.utils.url_args import url_from_message_args


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("video", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /video <url>\n"
            "Ejemplo: /video https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        return

    msg = update.effective_message
    limiter = limiter_from(context)
    user_id = user.id if user else None
    if user_id is None:
        return
    if not limiter.allow(user_id):
        stats.mark_rate_limited()
        await msg.reply_text(
            "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo."
        )
        return

    job = await queue_from(context).enqueue(
        context.application,
        kind="video",
        url=url,
        chat_id=update.effective_chat.id,
        user_id=user_id,
    )
    await msg.reply_text(f"Trabajo en cola: #{job.id} (video). Usa /jobs para ver estado.")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("video", cmd_video))
