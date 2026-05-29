"""Parte 1 — Menú principal (teclado inline y textos guía por callback)."""

from __future__ import annotations

import html as _html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import queue_from, stats_from
from bot.texts import HELP_HTML, MENU_HINTS_HTML, WELCOME_HTML

MENU_PREFIX = "menu:"

_STATUS_EMOJI: dict[str, str] = {
    "queued": "⏳",
    "running": "🔄",
    "done": "✅",
    "failed": "❌",
}
_KIND_LABEL: dict[str, str] = {"audio": "Audio", "video": "Video", "apple": "M4A"}
_AUDIO_FMTS: dict[str, str] = {"mp3": "MP3", "m4a": "M4A", "opus": "OPUS", "flac": "FLAC"}
_AUDIO_FMT_CB = "afmt:"  # must match the prefix in audio.py


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📚 Buscar libro", callback_data=f"{MENU_PREFIX}books")],
            [
                InlineKeyboardButton("🎵 Audio", callback_data=f"{MENU_PREFIX}audio"),
                InlineKeyboardButton("🎬 Video", callback_data=f"{MENU_PREFIX}video"),
            ],
            [
                InlineKeyboardButton("🎧 Formato audio", callback_data=f"{MENU_PREFIX}fmt_audio"),
                InlineKeyboardButton("📋 Mis trabajos", callback_data=f"{MENU_PREFIX}jobs"),
            ],
            [InlineKeyboardButton("❓ Ayuda", callback_data=f"{MENU_PREFIX}help")],
        ],
    )


def _back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("← Menú principal", callback_data=f"{MENU_PREFIX}back")]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.effective_message or context.user_data is None:
        return
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

    # ── Trabajos actuales del usuario ────────────────────────────────────────
    if action == "jobs":
        user = update.effective_user
        if user is None:
            return
        jobs = queue_from(context).jobs_for_user(user.id)
        if not jobs:
            text = (
                "<b>📋 Mis trabajos</b>\n\n"
                "No tienes trabajos recientes.\n"
                "Usa /audio, /video o envía una URL."
            )
        else:
            lines = ["<b>📋 Mis trabajos recientes</b>"]
            for job in jobs[:6]:
                emoji = _STATUS_EMOJI.get(job.status, "•")
                kind = _KIND_LABEL.get(job.kind, job.kind)
                line = f"{emoji} <code>#{job.id}</code> {kind}"
                if job.status == "running" and job.retry_count > 0:
                    line += f" — intento {job.retry_count + 1}"
                if job.error:
                    line += f"\n   ↳ {_html.escape(job.error[:80])}"
                lines.append(line)
            text = "\n".join(lines)
        try:
            await query.edit_message_text(text=text, reply_markup=main_menu_markup(), parse_mode="HTML")
        except Exception:
            if query.message:
                await query.message.reply_html(text, reply_markup=main_menu_markup())
        return

    # ── Selector de formato de audio ─────────────────────────────────────────
    if action == "fmt_audio":
        current = (context.user_data or {}).get("audio_format", "mp3")
        fmt_buttons = [
            InlineKeyboardButton(
                f"{'✅ ' if key == current else ''}{label}",
                callback_data=f"{_AUDIO_FMT_CB}{key}",
            )
            for key, label in _AUDIO_FMTS.items()
        ]
        markup = InlineKeyboardMarkup([fmt_buttons, _back_row()])
        text = (
            f"🎧 <b>Formato de audio</b>\n\n"
            f"Actual: <b>{_AUDIO_FMTS.get(current, current)}</b>\n\n"
            "Elige el formato para las próximas descargas de audio:"
        )
        try:
            await query.edit_message_text(text=text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            pass
        return

    # ── Volver al menú ───────────────────────────────────────────────────────
    if action == "back":
        try:
            await query.edit_message_text(
                text=WELCOME_HTML,
                reply_markup=main_menu_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    # ── Hints de comandos ────────────────────────────────────────────────────
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
        if query.message:
            await query.message.reply_html(text, reply_markup=reply_markup)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(
        CallbackQueryHandler(on_menu_callback, pattern=r"^menu:"),
    )
