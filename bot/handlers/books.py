"""Libros — búsqueda vía API REST y descarga al elegir resultado."""

from __future__ import annotations

import html
import io
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import http_session_from, limiter_from, settings_from, stats_from
from bot.handlers import menu
from bot.services.books_api import BookResult, BooksApiError, download_book_bytes, search_books
from bot.services.gutenberg import download_gutenberg, search_gutenberg
from bot.services.libgen import download_libgen, search_libgen
from bot.services.open_library import search_open_library

logger = logging.getLogger(__name__)

BOOK_PREFIX = "book:"
BOOK_SOURCES = ("gutenberg", "libgen", "open_library")
SOURCE_LABELS = {
    "gutenberg": "Gutenberg",
    "libgen": "Libgen",
    "open_library": "Open Library",
}


def _button_label(title: str, *, max_len: int = 58) -> str:
    t = title.strip() or "Sin título"
    return t if len(t) <= max_len else f"{t[: max_len - 3]}..."


async def cmd_fuente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("fuente", user.id if user else None)

    msg = update.effective_message
    args = context.args or []
    if not args:
        current = context.user_data.get("book_source", "open_library")
        label = SOURCE_LABELS.get(current, current)
        await msg.reply_text(
            "Selecciona la fuente de libros con /fuente <opción>. Opciones: gutenberg, libgen, open_library.\n"
            f"Fuente actual: {label}"
        )
        return

    choice = args[0].strip().lower()
    if choice not in BOOK_SOURCES:
        await msg.reply_text(
            "Fuente no válida. Usa /fuente gutenberg, /fuente libgen o /fuente open_library."
        )
        return

    context.user_data["book_source"] = choice
    await msg.reply_text(f"Fuente guardada: {SOURCE_LABELS[choice]}")


async def cmd_convertir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("convertir", user.id if user else None)
    msg = update.effective_message
    args = context.args or []

    if not args:
        await msg.reply_html(
            "<b>Conversión de libros</b>\n"
            "Primero envía un PDF o EPUB al bot.\n"
            "Luego usa: <code>/convertir &lt;formato&gt;</code>\n"
            "Formatos: epub, pdf, mobi, azw3, txt\n\n"
            "Ejemplo: <code>/convertir epub</code>"
        )
        return

    output_format = args[0].strip().lower()
    valid_formats = {"epub", "pdf", "mobi", "azw3", "txt"}
    if output_format not in valid_formats:
        await msg.reply_text(
            f"Formato no válido. Usa uno de: {', '.join(sorted(valid_formats))}"
        )
        return

    last_file = context.user_data.get("last_uploaded_file")
    if not last_file:
        await msg.reply_text(
            "No hay archivo reciente. Envía un PDF o EPUB primero."
        )
        return

    last_path = Path(last_file)
    if not last_path.exists():
        await msg.reply_text(
            "El archivo ya no está disponible. Envíalo de nuevo."
        )
        context.user_data.pop("last_uploaded_file", None)
        return

    await msg.reply_text(f"Convirtiendo a {output_format.upper()}...")

    try:
        from bot.utils.converter import ConversionError, convert_book
        output_path = await convert_book(last_path, output_format)
        with output_path.open("rb") as f:
            await msg.reply_document(
                document=InputFile(f, filename=output_path.name),
                read_timeout=600,
                write_timeout=600,
                connect_timeout=60,
            )
        stats_from(context).mark_download(ok=True)
    except Exception as exc:
        from bot.utils.converter import ConversionError
        stats_from(context).mark_download(ok=False)
        if isinstance(exc, ConversionError):
            await msg.reply_text(f"Error de conversión: {exc}")
        else:
            await msg.reply_text("Error al enviar el archivo convertido.")


async def cmd_libro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("libro", user.id if user else None)

    msg = update.effective_message
    q = " ".join(context.args).strip() if context.args else ""
    if not q:
        await msg.reply_html(
            "Uso: <code>/libro &lt;título o autor&gt;</code>\n\n"
            "Ejemplo: <code>/libro nombre del libro</code>",
            reply_markup=menu.main_menu_markup(),
        )
        return

    settings = settings_from(context)
    user_id = user.id if user else None
    if user_id is None:
        return
    if not limiter_from(context).allow(user_id):
        stats.mark_rate_limited()
        await msg.reply_text(
            "Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo."
        )
        return

    session = http_session_from(context)
    book_source = context.user_data.get("book_source")
    if book_source not in BOOK_SOURCES:
        if settings.books_api_enabled:
            book_source = "api"
        else:
            book_source = "open_library"

    try:
        if book_source == "gutenberg":
            results = await search_gutenberg(session, q, settings.books_api_max_results)
        elif book_source == "libgen":
            results = await search_libgen(q, settings.books_api_max_results)
        elif book_source == "open_library":
            results = await search_open_library(session, q, settings.books_api_max_results)
        else:
            results = await search_books(session, settings, q)
            book_source = "api"
    except BooksApiError as e:
        logger.info("libro búsqueda: %s", e)
        await msg.reply_text(str(e))
        return

    if not results:
        await msg.reply_text("No encontré resultados para esa búsqueda.")
        return

    context.user_data["books_pending"] = [
        {"id": r.id, "title": r.title, "source": book_source} for r in results
    ]
    keyboard = [
        [
            InlineKeyboardButton(
                _button_label(r.title),
                callback_data=f"{BOOK_PREFIX}{i}",
            ),
        ]
        for i, r in enumerate(results)
    ]
    safe_q = html.escape(q)
    await msg.reply_html(
        f"Resultados para <b>{safe_q}</b>. Pulsa uno:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def on_book_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()

    raw = (query.data or "").removeprefix(BOOK_PREFIX)
    try:
        idx = int(raw)
    except ValueError:
        return

    pending = context.user_data.get("books_pending")
    if not isinstance(pending, list) or idx < 0 or idx >= len(pending):
        try:
            await query.edit_message_text("Selección no válida o expirada. Usa /libro de nuevo.")
        except Exception:
            await query.message.reply_text("Selección no válida o expirada. Usa /libro de nuevo.")
        return

    item = pending[idx]
    book_id = str(item.get("id", "")).strip()
    if not book_id:
        await query.message.reply_text("ID de libro inválido.")
        return

    settings = settings_from(context)
    stats = stats_from(context)
    session = http_session_from(context)
    source = str(item.get("source", context.user_data.get("books_source", "api")))

    if source == "open_library":
        await query.message.reply_text(f"Busca este libro en: https://openlibrary.org{book_id}")
        context.user_data.pop("books_pending", None)
        return

    try:
        await query.edit_message_text("Descargando libro…")
    except Exception:
        await query.message.reply_text("Descargando libro…")

    try:
        if source == "gutenberg":
            data, filename = await download_gutenberg(session, book_id, settings)
        elif source == "libgen":
            data, filename = await download_libgen(session, book_id, settings)
        else:
            data, filename = await download_book_bytes(session, settings, book_id)

        buf = io.BytesIO(data)
        buf.seek(0)
        await query.message.reply_document(
            document=InputFile(buf, filename=filename),
            read_timeout=600,
            write_timeout=600,
            connect_timeout=60,
        )
        stats.mark_download(ok=True)
    except BooksApiError as e:
        stats.mark_download(ok=False)
        logger.info("libro descarga: %s", e)
        await query.message.reply_text(str(e))
    except OSError:
        stats.mark_download(ok=False)
        logger.exception("libro: envío de documento")
        await query.message.reply_text("Error al enviar el archivo.")
    finally:
        context.user_data.pop("books_pending", None)


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(on_book_pick, pattern=r"^book:\d+$"))
    application.add_handler(CommandHandler("fuente", cmd_fuente))
    application.add_handler(CommandHandler("libro", cmd_libro))
    application.add_handler(CommandHandler("convertir", cmd_convertir))
