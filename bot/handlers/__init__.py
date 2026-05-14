"""Registro de todos los handlers de comandos."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import queue_from, stats_from
from bot.handlers import admin, audio, books, menu, uploads, video, estado, url_detect
from bot.texts import HELP_HTML


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("ayuda", user.id if user else None)
    if not update.effective_message:
        return
    await update.effective_message.reply_html(
        HELP_HTML,
        reply_markup=menu.main_menu_markup(),
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("ping", user.id if user else None)
    if not update.effective_message:
        return
    await update.effective_message.reply_text("pong")


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("jobs", user.id if user else None)
    if user is None or not update.effective_message:
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


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats_from(context).mark_command("cancelar", user.id if user else None)
    if user is None or not update.effective_message:
        return
        
    queue = queue_from(context)
    jobs = queue.jobs_for_user(user.id)
    queued_jobs = [j for j in jobs if j.status == "queued"]
    if not queued_jobs:
        await update.effective_message.reply_text("No tienes descargas pendientes en cola.")
        return

    # jobs_for_user returns sorted by created_at DESC → index 0 = most recent
    latest_job = queued_jobs[0]
    latest_job.cancel_requested = True
    latest_job.status = "failed"
    latest_job.error = "Cancelado por el usuario"

    await update.effective_message.reply_text(f"Descarga #{latest_job.id} cancelada.")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    import os
    git_sha = os.environ.get("GIT_SHA", "dev")
    await update.effective_message.reply_text(f"TelegramMediaBot\nVersión: {git_sha}")


def register_handlers(application: Application, admin_user_id: int) -> None:
    menu.register(application)
    application.add_handler(CommandHandler("ayuda", cmd_ayuda))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(CommandHandler("jobs", cmd_jobs))
    application.add_handler(CommandHandler("cancelar", cmd_cancelar))
    application.add_handler(CommandHandler("version", cmd_version))
    books.register(application)
    audio.register(application)
    video.register(application)
    uploads.register(application)
    estado.register(application)
    url_detect.register(application)
    admin.register(application, admin_user_id=admin_user_id)
