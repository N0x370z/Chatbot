"""Libros — conecta aquí tu backend de búsqueda y envío."""

from __future__ import annotations

import html

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import stats_from
from bot.handlers import menu


async def cmd_libro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("libro", user.id if user else None)
    q = " ".join(context.args).strip() if context.args else ""
    if not q:
        await update.effective_message.reply_html(
            "Uso: <code>/libro &lt;título o autor&gt;</code>\n\n"
            "Aún no hay integración: implementa la lógica en "
            "<code>bot/handlers/books.py</code>.",
            reply_markup=menu.main_menu_markup(),
        )
        return
    safe = html.escape(q)
    await update.effective_message.reply_html(
        f"Búsqueda recibida: <b>{safe}</b>\n\n"
        "Siguiente paso: enlaza tu API o base de datos en este handler.",
        reply_markup=menu.main_menu_markup(),
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("libro", cmd_libro))
