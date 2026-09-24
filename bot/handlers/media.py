"""Lógica común de /audio, /apple y /video: analizar el enlace y encolar."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from bot.deps import limiter_from, queue_from, stats_from
from bot.download_queue import JobKind
from bot.services import ytdlp_download

# Elementos de una playlist que se encolan como máximo de una vez.
MAX_PLAYLIST_ITEMS = 50
_EMOJI = {"audio": "🎵", "apple": "🎵", "video": "🎬"}


async def enqueue_from_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    url: str,
    kind: JobKind,
    label: str,
    audio_format: str = "mp3",
) -> None:
    """Aplica el rate limit, expande playlists y encola lo que quepa en la cola."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None:
        return

    stats = stats_from(context)
    if not limiter_from(context).allow(user.id):
        stats.mark_rate_limited()
        await message.reply_text("Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo.")
        return

    status = await message.reply_text("🔎 Analizando enlace...")
    urls = await asyncio.to_thread(ytdlp_download.extract_playlist, url)
    if not urls:
        await status.edit_text("❌ No se encontró contenido en el enlace.")
        return

    queue = queue_from(context)
    capacity = min(MAX_PLAYLIST_ITEMS, queue.free_slots())
    if capacity <= 0:
        await status.edit_text("La cola de descargas está llena. Inténtalo en unos minutos.")
        return

    jobs = []
    for item_url in urls[:capacity]:
        try:
            jobs.append(
                await queue.enqueue(
                    context.application,
                    kind=kind,
                    url=item_url,
                    chat_id=chat.id,
                    user_id=user.id,
                    audio_format=audio_format,
                )
            )
        except ValueError:  # URL no http(s) o cola llena por otra petición simultánea
            continue

    if not jobs:
        await status.edit_text("No se pudo encolar ninguna descarga para ese enlace.")
        return
    if len(urls) == 1:
        text = f"Trabajo en cola: #{jobs[0].id} ({label}). Usa /jobs para ver estado."
    else:
        text = f"{_EMOJI[kind]} Playlist detectada. Añadidos {len(jobs)} trabajos a la cola ({label})."
        if len(jobs) < len(urls):
            text += f"\nSe omitieron {len(urls) - len(jobs)} por el límite de la cola; envíalos más tarde."
        text += "\nUsa /jobs para ver estado."
    await status.edit_text(text)
