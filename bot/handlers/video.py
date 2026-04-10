"""Video: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes
from yt_dlp.utils import DownloadError

from bot.deps import limiter_from, settings_from, stats_from
from bot.services.ytdlp_download import (
    DownloadTooLargeError,
    cleanup_download,
    download_best_video,
)
from bot.utils.telegram_upload import reply_with_video_or_document
from bot.utils.url_args import url_from_message_args

logger = logging.getLogger(__name__)


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
    chat = update.effective_chat
    settings = settings_from(context)
    limiter = limiter_from(context)
    user_id = user.id if user else None
    if user_id is None or not limiter.allow(user_id):
        stats.mark_rate_limited()
        await msg.reply_text(
            "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo."
        )
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VIDEO)
    status = await msg.reply_text("Descargando vídeo… (puede tardar bastante)")

    path = None
    try:
        path = await asyncio.to_thread(download_best_video, url, settings)
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VIDEO)
        await reply_with_video_or_document(msg, path)
        stats.mark_download(ok=True)
    except DownloadTooLargeError:
        stats.mark_download(ok=False)
        await msg.reply_text(
            f"El archivo supera el límite de {settings.max_file_size_mb} MB."
        )
    except ValueError as e:
        stats.mark_download(ok=False)
        await msg.reply_text(str(e))
    except DownloadError as e:
        stats.mark_download(ok=False)
        logger.warning("yt-dlp video: %s", e)
        await msg.reply_text(
            "No se pudo descargar el vídeo. Comprueba la URL y que FFmpeg esté instalado."
        )
    except OSError:
        stats.mark_download(ok=False)
        logger.exception("video: envío de archivo")
        await msg.reply_text("Error al leer o enviar el archivo.")
    finally:
        try:
            await status.delete()
        except Exception:
            pass
        if path is not None and path.exists():
            cleanup_download(path)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("video", cmd_video))
