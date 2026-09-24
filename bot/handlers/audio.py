"""Audio: descarga con yt-dlp (Parte 2)."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.deps import stats_from
from bot.handlers.media import enqueue_from_url
from bot.utils.url_args import url_from_message_args

AUDIO_FMT_PREFIX = "afmt:"
VALID_AUDIO_FMTS = {"mp3": "MP3", "m4a": "M4A (Apple)", "opus": "OPUS", "flac": "FLAC"}


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.effective_message or context.user_data is None:
        return
    stats_from(context).mark_command("audio", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /audio <url>\n"
            "Ejemplo: /audio https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\n"
            "Fuentes soportadas: YouTube, SoundCloud, Bandcamp.\n"
            "Apple Music y Spotify NO son compatibles por DRM."
        )
        return
    fmt = context.user_data.get("audio_format", "mp3")
    await enqueue_from_url(update, context, url=url, kind="audio", label=f"audio/{fmt.upper()}", audio_format=fmt)


async def cmd_apple(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.effective_message:
        return
    stats_from(context).mark_command("apple", user.id if user else None)
    url = url_from_message_args(context)
    if not url:
        await update.effective_message.reply_text(
            "Uso: /apple <url>\n"
            "Genera M4A cuando FFmpeg está disponible."
        )
        return
    await enqueue_from_url(update, context, url=url, kind="apple", label="apple")


async def cmd_formato_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or context.user_data is None:
        return
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
    if not query or not query.data or context.user_data is None:
        return
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
