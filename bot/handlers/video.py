"""Video: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

from bot.deps import limiter_from, queue_from, stats_from
from bot.services.ytdlp_download import extract_playlist
from bot.utils.url_args import url_from_message_args


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.effective_message or not update.effective_chat:
        return
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

    msg = await msg.reply_text("🔎 Analizando enlace...")
    urls = await asyncio.to_thread(extract_playlist, url)
    if not urls:
        await msg.edit_text("❌ No se encontró contenido en el enlace.")
        return
        
    urls = urls[:50]
    queue = queue_from(context)
    jobs = []
    for u in urls:
        job = await queue.enqueue(
            context.application,
            kind="video",
            url=u,
            chat_id=update.effective_chat.id,
            user_id=user_id,
        )
        jobs.append(job)
        
    if len(jobs) == 1:
        await msg.edit_text(f"Trabajo en cola: #{jobs[0].id} (video). Usa /jobs para ver estado.")
    else:
        await msg.edit_text(f"🎬 Playlist detectada. Añadidos {len(jobs)} trabajos a la cola (video). Usa /jobs para ver estado.")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("video", cmd_video))
