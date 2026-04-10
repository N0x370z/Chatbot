"""Registro de todos los handlers de comandos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import stats_from
from bot.handlers import admin, audio, books, menu, video
from bot.texts import HELP_HTML


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("ayuda", user.id if user else None)
    await update.effective_message.reply_html(
        HELP_HTML,
        reply_markup=menu.main_menu_markup(),
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("ping", user.id if user else None)
    await update.effective_message.reply_text("pong")


def register_handlers(application: Application, admin_user_id: int) -> None:
    menu.register(application)
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    application.add_handler(CommandHandler("ping", cmd_ping))
    books.register(application)
    audio.register(application)
    video.register(application)
    admin.register(application, admin_user_id=admin_user_id)
