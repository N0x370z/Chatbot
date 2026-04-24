"""Libros — búsqueda vía API REST y descarga al elegir resultado."""

from __future__ import annotations

import html
import io
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import http_session_from, limiter_from, settings_from, stats_from
from bot.handlers import menu
from bot.services.books_api import BookResult, BooksApiError, download_book_bytes, search_books

logger = logging.getLogger(__name__)

BOOK_PREFIX = "book:"


def _button_label(title: str, *, max_len: int = 58) -> str:
    t = title.strip() or "Sin título"
    return t if len(t) <= max_len else f"{t[: max_len - 3]}..."


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
    if not settings.books_api_enabled:
        await msg.reply_html(
            "Los libros requieren una API propia.\n\n"
            "Configura <code>BOOKS_API_BASE_URL</code> en <code>.env</code> "
            "(revisa <code>.env.example</code> y el docstring de "
            "<code>bot/services/books_api.py</code>).",
            reply_markup=menu.main_menu_markup(),
        )
        return

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
    try:
        results: list[BookResult] = await search_books(session, settings, q)
    except BooksApiError as e:
        logger.info("libro búsqueda: %s", e)
        await msg.reply_text(str(e))
        return

    if not results:
        await msg.reply_text("No encontré resultados para esa búsqueda.")
        return

    context.user_data["books_pending"] = [
        {"id": r.id, "title": r.title} for r in results
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

    try:
        await query.edit_message_text("Descargando libro…")
    except Exception:
        await query.message.reply_text("Descargando libro…")

    try:
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
    application.add_handler(CommandHandler("libro", cmd_libro))
