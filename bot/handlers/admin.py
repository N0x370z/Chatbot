"""Comandos de administración."""

from __future__ import annotations

from collections.abc import Iterable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import settings_from, stats_from


def _top_commands(items: Iterable[tuple[str, int]], n: int = 5) -> str:
    pairs = sorted(items, key=lambda t: t[1], reverse=True)[:n]
    if not pairs:
        return "sin datos"
    return ", ".join(f"/{name}:{count}" for name, count in pairs)


def register(application: Application, *, admin_user_id: int) -> None:
    async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings = settings_from(context)
        stats = stats_from(context)
        user = update.effective_user
        if admin_user_id == 0 or user is None or user.id != admin_user_id:
            await update.effective_message.reply_text(
                "No tienes permiso para este comando."
            )
            return
        stats.mark_command("stats", user.id)

        await update.effective_message.reply_text(
            "Estadísticas en memoria\n"
            f"- Uptime: {stats.uptime_human()}\n"
            f"- Usuarios únicos: {len(stats.unique_users)}\n"
            f"- Comandos totales: {stats.commands_total}\n"
            f"- Top comandos: {_top_commands(stats.command_counts.items())}\n"
            f"- Descargas OK/Fallidas: {stats.downloads_ok}/{stats.downloads_failed}\n"
            f"- Bloqueos por rate-limit: {stats.rate_limited_hits}\n"
            f"- Límite actual: {settings.rate_limit_max_requests} req / "
            f"{settings.rate_limit_window_sec}s"
        )

    application.add_handler(CommandHandler("stats", cmd_stats))
