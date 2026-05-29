"""Recepción y guardado de archivos subidos por usuarios."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from telegram import Document, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from bot.deps import settings_from, stats_from
from bot.services.calibre import CalibreError, add_to_calibre

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


def _verify_file_integrity(path: Path, extension: str) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        if extension == ".pdf":
            return header.startswith(b"%PDF")
        if extension == ".epub":
            return header.startswith(b"PK\x03\x04")
    except OSError:
        return False
    return True


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

    extension = Path(document.file_name or "").suffix.lower()
    mime_type = (document.mime_type or "").lower()

    if (extension == ".pdf" and mime_type == "application/epub+zip") or (extension == ".epub" and mime_type == "application/pdf"):
        warning_msg = f"Advertencia: la extensión del archivo ({extension}) no coincide con su tipo detectado ({mime_type})."
        logger.warning("Mismatch de extensión/MIME: nombre=%s mime=%s", document.file_name, mime_type)
        await message.reply_text(warning_msg)

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

    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_name = _safe_name(document.file_name, fallback=f"upload_{document.file_unique_id}")
    target = settings.incoming_files_path / f"{ts}_{safe_name}"
    tg_file = await document.get_file()
    await tg_file.download_to_drive(custom_path=str(target))

    if not _verify_file_integrity(target, extension):
        target.unlink(missing_ok=True)
        logger.warning("Integridad de archivo fallida: user_id=%s file=%s", user.id if user else "unknown", target)
        await message.reply_text("El archivo subido está corrupto o no tiene el formato correcto (no es un PDF ni EPUB válido).")
        return

    await message.reply_text(f"Archivo recibido: {target.name}")
    context.user_data["last_uploaded_file"] = str(target)
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
