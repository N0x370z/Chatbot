"""Libros — búsqueda, selección de fuente y descarga.

Flujo de la interfaz:
  /libro <consulta>  → mensaje con resultados (botones), paginación y
                       «🔁 Otra fuente» para repetir la búsqueda en otra.
  /fuente            → selector de fuente con botones (o /fuente <clave>).
Si la fuente elegida no da resultados, se consultan las demás en paralelo y
se muestran los de la primera (según prioridad) que responda.
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import io
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Message, Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import db_from, http_session_from, limiter_from, settings_from, stats_from
from bot.handlers import menu
from bot.services.books_api import BookResult, BooksApiError, download_book_bytes, search_books
from bot.services.sources import DEFAULT_SOURCE, SOURCES
from bot.utils.cache import BoundedTTLCache

logger = logging.getLogger(__name__)

BOOK_PREFIX = "book:"
PAGE_PREFIX = "bpage:"
SOURCE_PREFIX = "bsrc:"  # elegir fuente por defecto
RETRY_PREFIX = "bretry:"  # repetir la búsqueda actual en otra fuente
OTHER_SOURCES_CB = "bother"
API_SOURCE = "api"
BOOK_SOURCES = tuple(SOURCES)
# Límite por fuente al buscar en paralelo y por descarga completa.
SEARCH_DEADLINE_SEC = 25
DOWNLOAD_DEADLINE_SEC = 300


def _label(source: str) -> str:
    return SOURCES[source].label if source in SOURCES else "API propia"


def _default_source(settings) -> str:
    return API_SOURCE if settings.books_api_enabled else DEFAULT_SOURCE


def _current_source(context: ContextTypes.DEFAULT_TYPE) -> str:
    chosen = (context.user_data or {}).get("book_source")
    return chosen if chosen in SOURCES else _default_source(settings_from(context))


def _button_label(title: str, *, max_len: int = 58) -> str:
    t = title.strip() or "Sin título"
    return t if len(t) <= max_len else f"{t[: max_len - 3]}..."


# ── Teclados ─────────────────────────────────────────────────────────────────

def _build_books_keyboard(pending: list[dict], page: int, page_size: int) -> InlineKeyboardMarkup:
    start = page * page_size
    end = start + page_size
    keyboard = [
        [InlineKeyboardButton(_button_label(item["title"]), callback_data=f"{BOOK_PREFIX}{start + i}")]
        for i, item in enumerate(pending[start:end])
    ]
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"{PAGE_PREFIX}{page - 1}"))
    if end < len(pending):
        nav_row.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"{PAGE_PREFIX}{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔁 Otra fuente", callback_data=OTHER_SOURCES_CB)])
    return InlineKeyboardMarkup(keyboard)


def _sources_keyboard(prefix: str, current: str, *, back_cb: str | None = None) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if key == current else ''}{src.label}", callback_data=f"{prefix}{key}"
        )
        for key, src in SOURCES.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    if back_cb:
        rows.append([InlineKeyboardButton("⬅️ Volver", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _sources_text(current: str) -> str:
    lines = [f"<b>📚 Fuente de libros</b>\nActual: <b>{html.escape(_label(current))}</b>\n"]
    lines += [f"• <b>{s.label}</b> — {s.description}" for s in SOURCES.values()]
    lines.append("\nToca una fuente para usarla en tus próximas búsquedas.")
    return "\n".join(lines)


# ── /fuente ──────────────────────────────────────────────────────────────────

async def cmd_fuente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not msg or context.user_data is None:
        return
    stats_from(context).mark_command("fuente", user.id if user else None)
    args = context.args or []
    if not args:
        current = _current_source(context)
        await msg.reply_html(_sources_text(current), reply_markup=_sources_keyboard(SOURCE_PREFIX, current))
        return

    choice = args[0].strip().lower()
    if choice not in SOURCES:
        await msg.reply_text(f"Fuente no válida. Usa /fuente con una de: {', '.join(BOOK_SOURCES)}")
        return
    context.user_data["book_source"] = choice
    await msg.reply_text(f"Fuente guardada: {_label(choice)}")


async def on_source_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or context.user_data is None:
        return
    choice = (query.data or "").removeprefix(SOURCE_PREFIX)
    if choice in SOURCES:
        context.user_data["book_source"] = choice
        await query.answer(f"Fuente: {_label(choice)}")
    else:  # "show" desde el menú principal
        await query.answer()
    current = _current_source(context)
    with contextlib.suppress(TelegramError):
        await query.edit_message_text(
            _sources_text(current),
            parse_mode="HTML",
            reply_markup=_sources_keyboard(SOURCE_PREFIX, current),
        )


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


# ── Búsqueda ─────────────────────────────────────────────────────────────────

def _search_cache(context: ContextTypes.DEFAULT_TYPE) -> BoundedTTLCache:
    cache = context.application.bot_data.get("book_search_cache")
    if cache is None:
        cache = BoundedTTLCache(maxsize=100, ttl=300)
        context.application.bot_data["book_search_cache"] = cache
    return cache


async def _search_one(context: ContextTypes.DEFAULT_TYPE, source: str, q: str) -> list[BookResult]:
    """Busca en una fuente (con caché). Los errores se registran y devuelven []."""
    cache = _search_cache(context)
    cache_key = f"{source}:{q}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    settings = settings_from(context)
    session = http_session_from(context)
    try:
        async with asyncio.timeout(SEARCH_DEADLINE_SEC):
            if source in SOURCES:
                results = await SOURCES[source].search(
                    session, q, settings.books_api_max_results * 4, settings
                )
            else:
                results = await search_books(session, settings, q)
    except (BooksApiError, TimeoutError) as e:
        logger.info("libro búsqueda %s: %s", source, e or "timeout")
        return []
    except Exception:
        # Una fuente con un fallo inesperado no debe tumbar la búsqueda en paralelo.
        logger.exception("libro búsqueda %s: error inesperado", source)
        return []
    if results:
        cache.set(cache_key, results)
    return results


async def _search_with_fallback(
    context: ContextTypes.DEFAULT_TYPE, source: str, q: str
) -> tuple[list[BookResult], str]:
    results = await _search_one(context, source, q)
    if results:
        return results, source
    others = [key for key in SOURCES if key != source]
    all_results = await asyncio.gather(*(_search_one(context, key, q) for key in others))
    for key, found in zip(others, all_results, strict=True):
        if found:
            return found, key
    return [], source


def _results_text(q: str, source: str, requested: str) -> str:
    text = f"📚 Resultados para <b>{html.escape(q)}</b> en <i>{html.escape(_label(source))}</i>:"
    if source != requested:
        text += f"\n<i>({html.escape(_label(requested))} no dio resultados.)</i>"
    return text


def _store_results(context: ContextTypes.DEFAULT_TYPE, q: str, source: str, results: list[BookResult]) -> list[dict]:
    pending = [{"id": r.id, "title": r.title, "source": source} for r in results]
    context.user_data["books_pending"] = pending
    context.user_data["books_query"] = q
    context.user_data["books_results_source"] = source
    return pending


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
            "Ejemplo: <code>/libro don quijote</code>\n"
            "Cambia la fuente con /fuente.",
            reply_markup=menu.main_menu_markup(),
        )
        return

    if user is None:
        return
    if not limiter_from(context).allow(user.id):
        stats.mark_rate_limited()
        await msg.reply_text("Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.")
        return

    requested = _current_source(context)
    status = await msg.reply_html(f"🔎 Buscando <b>{html.escape(q)}</b>…")
    results, source = await _search_with_fallback(context, requested, q)

    if not results:
        text = "Ninguna fuente encontró resultados para esa búsqueda. Prueba con otras palabras."
        try:
            await status.edit_text(text)
        except TelegramError:
            await msg.reply_text(text)
        return

    pending = _store_results(context, q, source, results)
    settings = settings_from(context)
    keyboard = _build_books_keyboard(pending, 0, settings.books_api_max_results)
    text = _results_text(q, source, requested)
    try:
        await status.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramError:
        await msg.reply_html(text, reply_markup=keyboard)


async def on_book_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not isinstance(query.message, Message) or context.user_data is None:
        return
    await query.answer()
    try:
        page = int((query.data or "").removeprefix(PAGE_PREFIX))
    except ValueError:
        return

    pending = context.user_data.get("books_pending")
    if not isinstance(pending, list):
        with contextlib.suppress(TelegramError):
            await query.edit_message_text("Resultados expirados. Busca de nuevo.")
        return
    keyboard = _build_books_keyboard(pending, page, settings_from(context).books_api_max_results)
    with contextlib.suppress(TelegramError):
        await query.edit_message_reply_markup(reply_markup=keyboard)


async def on_other_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sustituye los resultados por la lista de fuentes para repetir la búsqueda."""
    query = update.callback_query
    if not query or context.user_data is None:
        return
    await query.answer()
    current = context.user_data.get("books_results_source", "")
    with contextlib.suppress(TelegramError):
        await query.edit_message_reply_markup(
            reply_markup=_sources_keyboard(RETRY_PREFIX, current, back_cb=f"{PAGE_PREFIX}0")
        )


async def on_retry_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user or context.user_data is None:
        return
    source = (query.data or "").removeprefix(RETRY_PREFIX)
    q = context.user_data.get("books_query")
    if source not in SOURCES or not q:
        await query.answer("Búsqueda expirada. Usa /libro de nuevo.", show_alert=True)
        return
    if not limiter_from(context).allow(user.id):
        stats_from(context).mark_rate_limited()
        await query.answer("Demasiadas solicitudes. Espera un momento.", show_alert=True)
        return
    await query.answer(f"Buscando en {_label(source)}…")

    results = await _search_one(context, source, q)
    if not results:
        with contextlib.suppress(TelegramError):
            await query.edit_message_text(
                f"Sin resultados para <b>{html.escape(q)}</b> en <i>{html.escape(_label(source))}</i>. "
                "Prueba otra fuente:",
                parse_mode="HTML",
                reply_markup=_sources_keyboard(RETRY_PREFIX, source),
            )
        return

    pending = _store_results(context, q, source, results)
    keyboard = _build_books_keyboard(pending, 0, settings_from(context).books_api_max_results)
    with contextlib.suppress(TelegramError):
        await query.edit_message_text(
            _results_text(q, source, source), parse_mode="HTML", reply_markup=keyboard
        )


# ── Descarga ─────────────────────────────────────────────────────────────────

async def _download_from_source(session, source: str, book_id: str, settings) -> tuple[bytes, str]:
    if source in SOURCES:
        return await SOURCES[source].download(session, book_id, settings)
    return await download_book_bytes(session, settings, book_id)


async def on_book_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not isinstance(query.message, Message) or context.user_data is None:
        return
    await query.answer()

    try:
        idx = int((query.data or "").removeprefix(BOOK_PREFIX))
    except ValueError:
        return

    pending = context.user_data.get("books_pending")
    if not isinstance(pending, list) or idx < 0 or idx >= len(pending):
        await query.message.reply_text("Selección no válida o expirada. Usa /libro de nuevo.")
        return

    item = pending[idx]
    book_id = str(item.get("id", "")).strip()
    if not book_id:
        await query.message.reply_text("ID de libro inválido.")
        return

    settings = settings_from(context)
    stats = stats_from(context)
    db = db_from(context)
    source = str(item.get("source") or _default_source(settings))
    file_cache_key = f"book:{source}:{book_id}"

    # El teclado de resultados se conserva para poder elegir otro libro si
    # este falla; el progreso va en un mensaje aparte que se borra al final.
    cached_file_id = await db.get_file_id(file_cache_key)
    if cached_file_id:
        try:
            await query.message.reply_document(document=cached_file_id, read_timeout=60, write_timeout=60)
            stats.mark_download(ok=True)
            return
        except TelegramError as e:
            logger.warning("Caché hit falló para %s: %s", file_cache_key, e)

    title = html.escape(str(item.get("title", "")).strip() or "libro")
    status_msg = await query.message.reply_html(
        f"⏳ Descargando <b>{title}</b> de {html.escape(_label(source))}…\n"
        "<i>Los archivos grandes pueden tardar un par de minutos.</i>"
    )

    try:
        async with asyncio.timeout(DOWNLOAD_DEADLINE_SEC):
            data, filename = await _download_from_source(
                http_session_from(context), source, book_id, settings
            )
        msg_out = await query.message.reply_document(
            document=InputFile(io.BytesIO(data), filename=filename),
            read_timeout=600,
            write_timeout=600,
            connect_timeout=60,
        )
        if msg_out and msg_out.document:
            await db.set_file_id(file_cache_key, msg_out.document.file_id)
        stats.mark_download(ok=True)
    except (BooksApiError, TimeoutError) as e:
        stats.mark_download(ok=False)
        reason = str(e) or "La descarga tardó demasiado."
        logger.info("libro descarga %s %s: %s", source, book_id, reason)
        await query.message.reply_text(f"{reason}\nPuedes elegir otro resultado de la lista.")
    except (OSError, TelegramError):
        stats.mark_download(ok=False)
        logger.exception("libro: envío de documento")
        await query.message.reply_text(
            "Error al enviar el archivo. Puede ser demasiado grande para Telegram; "
            "prueba con otro resultado."
        )
    finally:
        with contextlib.suppress(TelegramError):
            await status_msg.delete()


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(on_book_page, pattern=r"^bpage:\d+$"))
    application.add_handler(CallbackQueryHandler(on_book_pick, pattern=r"^book:\d+$"))
    application.add_handler(CallbackQueryHandler(on_source_pick, pattern=r"^bsrc:\w+$"))
    application.add_handler(CallbackQueryHandler(on_retry_source, pattern=r"^bretry:\w+$"))
    application.add_handler(CallbackQueryHandler(on_other_sources, pattern=r"^bother$"))
    application.add_handler(CommandHandler("fuente", cmd_fuente))
    application.add_handler(CommandHandler("libro", cmd_libro))
    application.add_handler(CommandHandler("convertir", cmd_convertir))
