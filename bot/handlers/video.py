"""Video: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes
from yt_dlp.utils import DownloadError

from bot.deps import settings_from
from bot.services.ytdlp_download import (
    DownloadTooLargeError,
    cleanup_download,
    download_best_video,
)
from bot.utils.telegram_upload import reply_with_video_or_document
from bot.utils.url_args import url_from_message_args

logger = logging.getLogger(__name__)


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VIDEO)
    status = await msg.reply_text("Descargando vídeo… (puede tardar bastante)")

    path = None
    try:
        path = await asyncio.to_thread(download_best_video, url, settings)
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VIDEO)
        await reply_with_video_or_document(msg, path)
    except DownloadTooLargeError:
        await msg.reply_text(
            f"El archivo supera el límite de {settings.max_file_size_mb} MB."
        )
    except ValueError as e:
        await msg.reply_text(str(e))
    except DownloadError as e:
        logger.warning("yt-dlp video: %s", e)
        await msg.reply_text(
            "No se pudo descargar el vídeo. Comprueba la URL y que FFmpeg esté instalado."
        )
    except OSError:
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
