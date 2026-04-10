"""Registro de todos los handlers de comandos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import queue_from, stats_from
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


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("jobs", user.id if user else None)
    if user is None:
        return
    jobs = queue_from(context).jobs_for_user(user.id)
    if not jobs:
        await update.effective_message.reply_text("No tienes trabajos recientes.")
        return
    lines = []
    for job in jobs:
        line = f"#{job.id} {job.kind} [{job.status}]"
        if job.error:
            line += f" - {job.error}"
        lines.append(line)
    await update.effective_message.reply_text("\n".join(lines))


def register_handlers(application: Application, admin_user_id: int) -> None:
    menu.register(application)
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(CommandHandler("jobs", cmd_jobs))
    books.register(application)
    audio.register(application)
    video.register(application)
    admin.register(application, admin_user_id=admin_user_id)
