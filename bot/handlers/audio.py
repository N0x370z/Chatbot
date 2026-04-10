"""Audio: descarga con yt-dlp (Parte 2)."""

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
    download_apple_m4a,
    download_best_audio,
)
from bot.utils.telegram_upload import reply_with_audio_or_document
from bot.utils.url_args import url_from_message_args

logger = logging.getLogger(__name__)


async def _send_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    url: str,
    download_fn,
) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    settings = settings_from(context)
    stats = stats_from(context)
    limiter = limiter_from(context)
    user_id = user.id if user else None

    if user_id is None or not limiter.allow(user_id):
        stats.mark_rate_limited()
        await msg.reply_text(
            "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo."
        )
        return

    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VOICE)
    status = await msg.reply_text("Descargando… (puede tardar unos minutos)")

    path = None
    try:
        path = await asyncio.to_thread(download_fn, url, settings)
        await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.UPLOAD_VOICE)
        await reply_with_audio_or_document(msg, path)
        stats.mark_download(ok=True)
    except DownloadTooLargeError:
        stats.mark_download(ok=False)
        await msg.reply_text(
            f"El archivo supera el límite de {settings.max_file_size_mb} MB. "
            "Ajusta MAX_FILE_SIZE_MB en .env si tu Telegram lo permite."
        )
    except ValueError as e:
        stats.mark_download(ok=False)
        await msg.reply_text(str(e))
    except DownloadError as e:
        stats.mark_download(ok=False)
        logger.warning("yt-dlp: %s", e)
        await msg.reply_text(
            "No se pudo descargar. Comprueba la URL, que FFmpeg esté "
            "instalado (`brew install ffmpeg`) y vuelve a intentarlo."
        )
    except OSError:
        stats.mark_download(ok=False)
        logger.exception("audio: envío de archivo")
        await msg.reply_text("Error al leer o enviar el archivo.")
    finally:
        try:
            await status.delete()
        except Exception:
            pass
        if path is not None and path.exists():
            cleanup_download(path)


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("audio", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /audio <url>\n"
            "Ejemplo: /audio https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        return
    await _send_audio(update, context, url=url, download_fn=download_best_audio)


async def cmd_apple(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("apple", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /apple <url>\n"
            "Genera M4A cuando FFmpeg está disponible."
        )
        return
    await _send_audio(update, context, url=url, download_fn=download_apple_m4a)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("audio", cmd_audio))
    application.add_handler(CommandHandler("apple", cmd_apple))
