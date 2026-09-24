"""Recepción y guardado de archivos subidos por usuarios.

El archivo se descarga con un nombre temporal (``.part``), se valida y solo
entonces se renombra dentro de ``INCOMING_FILES_PATH``. Así el worker, que
mueve a ``processed`` todo PDF/EPUB que aparece ahí, nunca ve un archivo a
medio escribir. Como el worker se lo lleva, para ``/convertir`` se guarda el
``file_id`` de Telegram y se vuelve a descargar si hace falta.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from telegram import Document, Update
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from bot.deps import settings_from, stats_from
from bot.services._book_validation import detect_book_type
from bot.services.calibre import CalibreError, add_to_calibre

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".epub"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/epub+zip"}
_MIME_EXTENSION = {"application/pdf": ".pdf", "application/epub+zip": ".epub"}
# La Bot API no permite a los bots descargar archivos de más de 20 MB.
TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024


def _book_extension(document: Document) -> str | None:
    """Extensión efectiva (.pdf/.epub) por nombre o, si no, por tipo MIME."""
    extension = Path(document.file_name or "").suffix.lower()
    if extension in ALLOWED_EXTENSIONS:
        return extension
    return _MIME_EXTENSION.get((document.mime_type or "").lower())


def _is_supported(document: Document) -> bool:
    return _book_extension(document) is not None


def _safe_name(name: str | None, fallback: str) -> str:
    original = (name or "").strip()
    if not original:
        return fallback
    return Path(original).name


def _verify_file_integrity(path: Path, extension: str) -> bool:
    """El contenido (magic bytes) coincide con la extensión .pdf/.epub."""
    try:
        with open(path, "rb") as f:
            header = f.read(4)
    except OSError:
        return False
    return f".{detect_book_type(header)}" == extension


def upload_limit_bytes(settings) -> int:
    return min(settings.max_upload_size_bytes, TELEGRAM_DOWNLOAD_LIMIT)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    document = message.document if message else None
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("upload", user.id if user else None)
    if document is None or message is None or context.user_data is None:
        return
    extension = _book_extension(document)
    if extension is None:
        await message.reply_text("Solo acepto archivos PDF o EPUB.")
        logger.info("Archivo rechazado: nombre=%s mime=%s", document.file_name, document.mime_type)
        return

    settings = settings_from(context)
    limit = upload_limit_bytes(settings)
    if document.file_size and document.file_size > limit:
        await message.reply_text(
            f"El archivo supera el límite de {limit // (1024 * 1024)} MB "
            "(Telegram no deja a los bots descargar archivos más grandes)."
        )
        logger.info("Archivo excede límite: nombre=%s size=%s", document.file_name, document.file_size)
        return

    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_name = _safe_name(document.file_name, fallback=f"upload_{document.file_unique_id}")
    target = settings.incoming_files_path / f"{ts}_{Path(safe_name).stem}{extension}"
    partial = target.with_name(f".{target.name}.part")
    try:
        tg_file = await document.get_file()
        await tg_file.download_to_drive(custom_path=str(partial))
    except TelegramError as e:
        partial.unlink(missing_ok=True)
        logger.warning("No se pudo descargar el archivo subido: %s", e)
        await message.reply_text("No pude descargar el archivo desde Telegram. Inténtalo de nuevo.")
        return

    if not _verify_file_integrity(partial, extension):
        partial.unlink(missing_ok=True)
        logger.warning("Integridad de archivo fallida: user_id=%s file=%s", user.id if user else "unknown", target)
        await message.reply_text(
            f"El archivo no es un {extension[1:].upper()} válido (puede estar corrupto)."
        )
        return
    os.replace(partial, target)

    context.user_data["last_uploaded_file"] = str(target)
    context.user_data["last_uploaded_file_id"] = document.file_id
    await message.reply_text(
        f"Archivo recibido: {target.name}\nConviértelo con /convertir <formato> (epub, pdf, mobi, azw3, txt)."
    )
    logger.info(
        "Archivo guardado: user_id=%s name=%s size=%s path=%s",
        user.id if user else "unknown",
        document.file_name,
        document.file_size,
        target,
    )
    if settings.calibre_library_path is not None:
        try:
            out = await add_to_calibre(target, settings.calibre_library_path)
            logger.info(
                "Archivo agregado a Calibre: file=%s library=%s out=%s",
                target,
                settings.calibre_library_path,
                out,
            )
        except CalibreError as e:
            logger.warning("Calibre rechazó archivo %s: %s", target, e)
            await message.reply_text("No se pudo agregar el archivo a Calibre.")


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
