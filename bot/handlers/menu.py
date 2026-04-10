"""Parte 1 — Menú principal (teclado inline y textos guía por callback)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import stats_from
from bot.texts import HELP_HTML, MENU_HINTS_HTML, WELCOME_HTML

MENU_PREFIX = "menu:"


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Libros", callback_data=f"{MENU_PREFIX}books")],
            [
                InlineKeyboardButton("Audio", callback_data=f"{MENU_PREFIX}audio"),
                InlineKeyboardButton("Video", callback_data=f"{MENU_PREFIX}video"),
            ],
            [InlineKeyboardButton("Apple (M4A)", callback_data=f"{MENU_PREFIX}apple")],
            [InlineKeyboardButton("Ayuda", callback_data=f"{MENU_PREFIX}help")],
        ],
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("start", user.id if user else None)
    await update.effective_message.reply_html(
        WELCOME_HTML,
        reply_markup=main_menu_markup(),
    )


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    action = (query.data or "").removeprefix(MENU_PREFIX)

    if action == "help":
        text, reply_markup = HELP_HTML, main_menu_markup()
    elif action in MENU_HINTS_HTML:
        text, reply_markup = MENU_HINTS_HTML[action], main_menu_markup()
    else:
        text, reply_markup = HELP_HTML, main_menu_markup()

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except Exception:
        await query.message.reply_html(text, reply_markup=reply_markup)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(
        CallbackQueryHandler(on_menu_callback, pattern=r"^menu:"),
    )
