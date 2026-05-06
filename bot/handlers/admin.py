"""Comandos de administración."""

from __future__ import annotations

from collections.abc import Iterable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import db_from, settings_from, stats_from


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

    async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if admin_user_id == 0 or user is None or user.id != admin_user_id:
            return
        
        args = context.args
        if not args or not args[0].isdigit():
            await update.effective_message.reply_text("Uso: /ban <user_id>")
            return
            
        target_id = int(args[0])
        await db_from(context).set_banned(target_id, True)
        await update.effective_message.reply_text(f"Usuario {target_id} ha sido baneado.")

    async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if admin_user_id == 0 or user is None or user.id != admin_user_id:
            return
        
        args = context.args
        if not args or not args[0].isdigit():
            await update.effective_message.reply_text("Uso: /unban <user_id>")
            return
            
        target_id = int(args[0])
        await db_from(context).set_banned(target_id, False)
        await update.effective_message.reply_text(f"Usuario {target_id} ha sido desbaneado.")

    async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if admin_user_id == 0 or user is None or user.id != admin_user_id:
            return
            
        msg_text = " ".join(context.args)
        if not msg_text:
            await update.effective_message.reply_text("Uso: /broadcast <mensaje>")
            return
            
        await update.effective_message.reply_text("Enviando broadcast...")
        users = await db_from(context).get_all_users()
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=msg_text)
                sent += 1
            except Exception:
                pass
        await update.effective_message.reply_text(f"Broadcast enviado a {sent} usuarios de {len(users)}.")

    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
