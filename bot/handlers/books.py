"""Libros — búsqueda vía API REST y descarga al elegir resultado."""

from __future__ import annotations

import contextlib
import html
import io
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Message, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import db_from, http_session_from, limiter_from, settings_from, stats_from
from bot.handlers import menu
from bot.services.books_api import BookResult, BooksApiError, download_book_bytes, search_books
from bot.services.dbooks import download_dbooks, search_dbooks
from bot.services.gutenberg import download_gutenberg, search_gutenberg
from bot.services.internet_archive import download_internet_archive, search_internet_archive
from bot.services.libgen import download_libgen, search_libgen
from bot.services.open_library import search_open_library
from bot.services.standard_ebooks import download_standard_ebooks, search_standard_ebooks
from bot.utils.cache import BoundedTTLCache

logger = logging.getLogger(__name__)

BOOK_PREFIX = "book:"
BOOK_SOURCES = ("gutenberg", "libgen", "open_library", "dbooks", "internet_archive", "standard_ebooks")
FALLBACK_CHAIN = ("open_library", "internet_archive", "dbooks", "libgen", "gutenberg", "standard_ebooks")
SOURCE_LABELS = {
    "gutenberg": "Gutenberg",
    "libgen": "Libgen",
    "open_library": "Open Library",
    "dbooks": "DBooks",
    "internet_archive": "Internet Archive",
    "standard_ebooks": "Standard Ebooks",
}


def _button_label(title: str, *, max_len: int = 58) -> str:
    t = title.strip() or "Sin título"
    return t if len(t) <= max_len else f"{t[: max_len - 3]}..."


def _build_books_keyboard(pending: list[dict], page: int, page_size: int) -> InlineKeyboardMarkup:
    start = page * page_size
    end = start + page_size
    page_items = pending[start:end]

    keyboard = [
        [
            InlineKeyboardButton(
                _button_label(item["title"]),
                callback_data=f"{BOOK_PREFIX}{start + i}",
            )
        ]
        for i, item in enumerate(page_items)
    ]

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"bpage:{page - 1}"))
    if end < len(pending):
        nav_row.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"bpage:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    return InlineKeyboardMarkup(keyboard)


async def cmd_fuente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not msg or context.user_data is None:
        return
    stats = stats_from(context)
    stats.mark_command("fuente", user.id if user else None)
    args = context.args or []
    if not args:
        current = context.user_data.get("book_source", "standard_ebooks")
        label = SOURCE_LABELS.get(current, current)
        sources_list = ", ".join(BOOK_SOURCES)
        await msg.reply_text(
            f"Selecciona la fuente de libros con /fuente <opción>.\n"
            f"Opciones: {sources_list}\n"
            f"Fuente actual: {label}"
        )
        return

    choice = args[0].strip().lower()
    if choice not in BOOK_SOURCES:
        sources_list = ", ".join(BOOK_SOURCES)
        await msg.reply_text(
            f"Fuente no válida. Usa /fuente con una de: {sources_list}"
        )
        return

    context.user_data["book_source"] = choice
    await msg.reply_text(f"Fuente guardada: {SOURCE_LABELS[choice]}")


async def cmd_convertir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not msg or context.user_data is None:
        return
    stats_from(context).mark_command("convertir", user.id if user else None)
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

        if last_path.suffix.lower() == f".{output_format}":
            await msg.reply_text(
                f"El archivo ya está en formato {output_format.upper()}. "
                "No es necesario convertirlo."
            )
            return

        status_msg = await msg.reply_text(
            f"⏳ Convirtiendo a {output_format.upper()}, esto puede tardar unos segundos..."
        )
        output_path = await convert_book(last_path, output_format)

        with output_path.open("rb") as f:
            await msg.reply_document(
                document=InputFile(f, filename=output_path.name),
                read_timeout=600,
                write_timeout=600,
                connect_timeout=60,
            )
        await status_msg.delete()
        stats_from(context).mark_download(ok=True)
        with contextlib.suppress(OSError):
            output_path.unlink(missing_ok=True)
    except Exception as exc:
        from bot.utils.converter import ConversionError
        stats_from(context).mark_download(ok=False)
        if isinstance(exc, ConversionError):
            await msg.reply_text(f"Error de conversión: {exc}")
        else:
            logger.exception("convertir: error inesperado")
            await msg.reply_text("Error al enviar el archivo convertido.")


async def _search_source(session, source: str, q: str, limit: int, settings) -> list[BookResult]:
    if source == "gutenberg":
        return await search_gutenberg(session, q, limit)
    if source == "libgen":
        return await search_libgen(session, q, limit, settings)
    if source == "open_library":
        return await search_open_library(session, q, limit)
    if source == "dbooks":
        return await search_dbooks(session, q, limit)
    if source == "internet_archive":
        return await search_internet_archive(session, q, limit)
    if source == "standard_ebooks":
        return await search_standard_ebooks(session, q, limit)
    return await search_books(session, settings, q)


async def cmd_libro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not msg or context.user_data is None:
        return
    stats = stats_from(context)
    stats.mark_command("libro", user.id if user else None)
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
        book_source = "api" if settings.books_api_enabled else "open_library"

    cache = context.application.bot_data.get("book_search_cache")
    if cache is None:
        cache = BoundedTTLCache(maxsize=100, ttl=300)
        context.application.bot_data["book_search_cache"] = cache

    fetch_limit = settings.books_api_max_results * 4
    results: list[BookResult] = []
    effective_source = book_source
    fallback_used: str | None = None

    cached = cache.get(f"{book_source}:{q}")
    if cached is not None:
        logger.debug("book cache hit for %s:%s", book_source, q)
        results = cached
    else:
        logger.debug("book cache miss for %s:%s", book_source, q)
        try:
            results = await _search_source(session, book_source, q, fetch_limit, settings)
        except BooksApiError as e:
            logger.info("libro búsqueda %s: %s", book_source, e)
        if results:
            cache.set(f"{book_source}:{q}", results)

    if not results:
        for fb in FALLBACK_CHAIN:
            if fb == book_source:
                continue
            cached_fb = cache.get(f"{fb}:{q}")
            if cached_fb is not None:
                results = cached_fb
                effective_source = fb
                fallback_used = fb
                break
            try:
                results = await _search_source(session, fb, q, fetch_limit, settings)
            except BooksApiError as e:
                logger.info("libro fallback %s: %s", fb, e)
                continue
            if results:
                cache.set(f"{fb}:{q}", results)
                effective_source = fb
                fallback_used = fb
                break

    if not results:
        await msg.reply_text(
            "Ninguna fuente respondió para esa búsqueda. Inténtalo de nuevo más tarde."
        )
        return

    context.user_data["books_pending"] = [
        {"id": r.id, "title": r.title, "source": effective_source} for r in results
    ]

    keyboard = _build_books_keyboard(context.user_data["books_pending"], 0, settings.books_api_max_results)
    safe_q = html.escape(q)
    fallback_note = (
        f"\n<i>(usando {html.escape(SOURCE_LABELS.get(fallback_used, fallback_used))} como respaldo)</i>"
        if fallback_used else ""
    )
    await msg.reply_html(
        f"Resultados para <b>{safe_q}</b>:{fallback_note}",
        reply_markup=keyboard,
    )


async def on_book_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or context.user_data is None:
        return
    if not isinstance(query.message, Message):
        return
    await query.answer()

    try:
        page = int((query.data or "").removeprefix("bpage:"))
    except ValueError:
        return

    pending = context.user_data.get("books_pending")
    if not isinstance(pending, list):
        with contextlib.suppress(Exception):
            await query.edit_message_text("Resultados expirados. Busca de nuevo.")
        return

    settings = settings_from(context)
    keyboard = _build_books_keyboard(pending, page, settings.books_api_max_results)

    with contextlib.suppress(Exception):
        await query.edit_message_reply_markup(reply_markup=keyboard)


async def on_book_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or context.user_data is None:
        return
    if not isinstance(query.message, Message):
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
    source = str(item.get("source", context.user_data.get("book_source", "api")))

    if source == "open_library":
        await query.message.reply_text(
            "Open Library es un catálogo bibliográfico, no aloja archivos descargables.\n\n"
            "Para obtener el archivo directamente, cambia la fuente con:\n"
            "/fuente standard_ebooks — libros clásicos en ediciones cuidadas\n"
            "/fuente gutenberg — mayor catálogo de dominio público\n\n"
            f"Referencia: https://openlibrary.org{book_id}"
        )
        context.user_data.pop("books_pending", None)
        return

    db = db_from(context)
    file_cache_key = f"book:{source}:{book_id}"

    # Try fast path via file_id
    cached_file_id = await db.get_file_id(file_cache_key)
    if cached_file_id:
        try:
            await query.edit_message_text("Enviando desde caché instantánea...")
            await query.message.reply_document(
                document=cached_file_id,
                read_timeout=60,
                write_timeout=60,
            )
            stats.mark_download(ok=True)
            context.user_data.pop("books_pending", None)
            return
        except Exception as e:
            logger.warning("Caché hit falló para %s: %s", file_cache_key, e)
            # fallback to normal download if Telegram rejected the file_id

    try:
        await query.edit_message_text("Descargando libro…")
    except Exception:
        await query.message.reply_text("Descargando libro…")

    try:
        if source == "gutenberg":
            data, filename = await download_gutenberg(session, book_id, settings)
        elif source == "libgen":
            data, filename = await download_libgen(session, book_id, settings)
        elif source == "dbooks":
            data, filename = await download_dbooks(session, book_id, settings)
        elif source == "internet_archive":
            data, filename = await download_internet_archive(session, book_id, settings)
        elif source == "standard_ebooks":
            data, filename = await download_standard_ebooks(session, book_id, settings)
        else:
            data, filename = await download_book_bytes(session, settings, book_id)

        buf = io.BytesIO(data)
        buf.seek(0)
        msg_out = await query.message.reply_document(
            document=InputFile(buf, filename=filename),
            read_timeout=600,
            write_timeout=600,
            connect_timeout=60,
        )
        if msg_out and msg_out.document:
            await db.set_file_id(file_cache_key, msg_out.document.file_id)
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
    application.add_handler(CallbackQueryHandler(on_book_page, pattern=r"^bpage:\d+$"))
    application.add_handler(CallbackQueryHandler(on_book_pick, pattern=r"^book:\d+$"))
    application.add_handler(CommandHandler("fuente", cmd_fuente))
    application.add_handler(CommandHandler("libro", cmd_libro))
    application.add_handler(CommandHandler("convertir", cmd_convertir))
