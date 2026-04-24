"""Recepción y guardado de archivos subidos por usuarios."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from telegram import Document, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from bot.deps import settings_from, stats_from

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".epub"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/epub+zip"}


def _is_supported(document: Document) -> bool:
    extension = Path(document.file_name or "").suffix.lower()
    mime_type = (document.mime_type or "").lower()
    return extension in ALLOWED_EXTENSIONS or mime_type in ALLOWED_MIME_TYPES


def _safe_name(name: str | None, fallback: str) -> str:
    original = (name or "").strip()
    if not original:
        return fallback
    return Path(original).name


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    document = message.document if message else None
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("upload", user.id if user else None)
    if document is None or message is None:
        return
    if not _is_supported(document):
        await message.reply_text("Solo acepto archivos PDF o EPUB.")
        logger.info("Archivo rechazado: nombre=%s mime=%s", document.file_name, document.mime_type)
        return

    settings = settings_from(context)
    if document.file_size and document.file_size > settings.max_upload_size_bytes:
        await message.reply_text(
            f"El archivo supera el límite de {settings.max_upload_size_mb} MB."
        )
        logger.info(
            "Archivo excede límite: nombre=%s size=%s",
            document.file_name,
            document.file_size,
        )
        return

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = _safe_name(document.file_name, fallback=f"upload_{document.file_unique_id}")
    target = settings.incoming_files_path / f"{ts}_{safe_name}"
    tg_file = await document.get_file()
    await tg_file.download_to_drive(custom_path=str(target))
    await message.reply_text(f"Archivo recibido y guardado: {target}")
    logger.info(
        "Archivo guardado: user_id=%s name=%s size=%s path=%s",
        user.id if user else "unknown",
        document.file_name,
        document.file_size,
        target,
    )


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.Document.ALL, on_document))
