"""Comandos de administración."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable

import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.deps import db_from, http_session_from, settings_from, stats_from


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
        if not update.effective_message or admin_user_id == 0 or user is None or user.id != admin_user_id:
            if update.effective_message:
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
        if not update.effective_message or admin_user_id == 0 or user is None or user.id != admin_user_id:
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
        if not update.effective_message or admin_user_id == 0 or user is None or user.id != admin_user_id:
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
        if not update.effective_message or admin_user_id == 0 or user is None or user.id != admin_user_id:
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

    _DIAG_PROBES = [
        ("Open Library",     "https://openlibrary.org/search.json?q=test&limit=1"),
        ("Gutendex",         "https://gutendex.com/books?search=test"),
        ("Standard Ebooks",  "https://standardebooks.org/feeds/opds"),
        ("dBooks",           "https://www.dbooks.org/api/search/test"),
        ("Internet Archive", "https://archive.org/advancedsearch.php?q=test&output=json&rows=1"),
        ("Libgen",           "https://libgen.li/index.php?req=test&res=1"),
    ]

    async def cmd_diagnostico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not update.effective_message or admin_user_id == 0 or user is None or user.id != admin_user_id:
            if update.effective_message:
                await update.effective_message.reply_text("No tienes permiso para este comando.")
            return

        session = http_session_from(context)
        timeout = aiohttp.ClientTimeout(total=10, connect=5)

        async def _probe(name: str, url: str) -> str:
            start = time.monotonic()
            try:
                async with session.get(url, timeout=timeout) as resp:
                    resp.raise_for_status()
                    ms = int((time.monotonic() - start) * 1000)
                    return f"✅ {name} — {ms}ms"
            except TimeoutError:
                return f"❌ {name} — timeout"
            except aiohttp.ClientError as exc:
                return f"❌ {name} — {exc.__class__.__name__}"

        lines = await asyncio.gather(*(_probe(n, u) for n, u in _DIAG_PROBES))
        await update.effective_message.reply_text("\n".join(lines))

    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
    application.add_handler(CommandHandler("diagnostico", cmd_diagnostico))
