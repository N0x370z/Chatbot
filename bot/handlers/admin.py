"""Comandos de administración."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


def register(application: Application, *, admin_user_id: int) -> None:
    async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if admin_user_id == 0 or user is None or user.id != admin_user_id:
            await update.effective_message.reply_text(
                "No tienes permiso para este comando."
            )
            return
        await update.effective_message.reply_text(
            "Estadísticas: lógica pendiente (bot/handlers/admin.py)."
        )

    application.add_handler(CommandHandler("stats", cmd_stats))
