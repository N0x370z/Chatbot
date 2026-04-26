"""Audio: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import limiter_from, queue_from, stats_from
from bot.utils.url_args import url_from_message_args

AUDIO_FMT_PREFIX = "afmt:"
VALID_AUDIO_FMTS = {"mp3": "MP3", "m4a": "M4A (Apple)", "opus": "OPUS", "flac": "FLAC"}


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("audio", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /audio <url>\n"
            "Ejemplo: /audio https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\n"
            "Fuentes soportadas: YouTube, SoundCloud, Bandcamp.\n"
            "Apple Music y Spotify NO son compatibles por DRM."
        )
        return
    user_id = user.id if user else None
    if user_id is None:
        return
    limiter = limiter_from(context)
    if not limiter.allow(user_id):
        stats.mark_rate_limited()
        await update.effective_message.reply_text(
            "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo."
        )
        return
    fmt = context.user_data.get("audio_format", "mp3")
    job = await queue_from(context).enqueue(
        context.application,
        kind="audio",
        url=url,
        chat_id=update.effective_chat.id,
        user_id=user_id,
        audio_format=fmt,
    )
    await update.effective_message.reply_text(
        f"Trabajo en cola: #{job.id} (audio/{fmt.upper()}). Usa /jobs para ver estado."
    )


async def cmd_apple(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    stats = stats_from(context)
    stats.mark_command("apple", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /apple <url>\n"
            "Genera M4A cuando FFmpeg está disponible."
        )
        return
    user_id = user.id if user else None
    if user_id is None:
        return
    limiter = limiter_from(context)
    if not limiter.allow(user_id):
        stats.mark_rate_limited()
        await update.effective_message.reply_text(
            "Demasiadas solicitudes seguidas. Espera un minuto e inténtalo de nuevo."
        )
        return
    job = await queue_from(context).enqueue(
        context.application,
        kind="apple",
        url=url,
        chat_id=update.effective_chat.id,
        user_id=user_id,
    )
    await update.effective_message.reply_text(
        f"Trabajo en cola: #{job.id} (apple). Usa /jobs para ver estado."
    )


async def cmd_formato_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = context.user_data.get("audio_format", "mp3")
    buttons = [
        [
            InlineKeyboardButton(text=label, callback_data=f"{AUDIO_FMT_PREFIX}{key}")
            for key, label in VALID_AUDIO_FMTS.items()
        ]
    ]
    await update.effective_message.reply_html(
        f"Formato actual: <b>{VALID_AUDIO_FMTS.get(current, current)}</b>\nElige:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def on_audio_fmt_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    fmt = query.data.removeprefix(AUDIO_FMT_PREFIX)
    if fmt not in VALID_AUDIO_FMTS:
        return
    context.user_data["audio_format"] = fmt
    await query.edit_message_text(
        f"✅ Formato de audio: <b>{VALID_AUDIO_FMTS[fmt]}</b>",
        parse_mode="HTML",
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("audio", cmd_audio))
    application.add_handler(CommandHandler("apple", cmd_apple))
    application.add_handler(CommandHandler("formato_audio", cmd_formato_audio))
    application.add_handler(CallbackQueryHandler(on_audio_fmt_pick, pattern=r"^afmt:"))
