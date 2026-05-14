"""Auto-detección de URL en mensajes de texto sin comando."""

from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from bot.deps import limiter_from, queue_from, stats_from

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

_AUDIO_DOMAINS = frozenset({
    "soundcloud.com",
    "bandcamp.com",
    "music.youtube.com",
})

URL_ACTION_PREFIX = "urlact:"


def _extract_url(text: str) -> str | None:
    m = _URL_RE.search(text)
    return m.group(0).rstrip(".,)>") if m else None


def _is_audio_domain(url: str) -> bool:
    url_lower = url.lower()
    return any(d in url_lower for d in _AUDIO_DOMAINS)


async def on_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not msg.text or not update.effective_chat or context.user_data is None:
        return

    url = _extract_url(msg.text)
    if not url:
        return

    stats = stats_from(context)
    stats.mark_command("url_auto", user.id)

    limiter = limiter_from(context)
    if not limiter.allow(user.id):
        stats.mark_rate_limited()
        await msg.reply_text("Demasiadas solicitudes seguidas. Espera un momento.")
        return

    # Guardamos la URL para el callback
    context.user_data["url_pending"] = url

    if _is_audio_domain(url):
        fmt = context.user_data.get("audio_format", "mp3")
        job = await queue_from(context).enqueue(
            context.application,
            kind="audio",
            url=url,
            chat_id=update.effective_chat.id,
            user_id=user.id,
            audio_format=fmt,
        )
        await msg.reply_text(
            f"🎵 Audio detectado automáticamente.\n"
            f"Trabajo en cola: #{job.id} ({fmt.upper()}). Usa /jobs para ver estado."
        )
    else:
        buttons = [[
            InlineKeyboardButton("🎵 Audio", callback_data=f"{URL_ACTION_PREFIX}audio"),
            InlineKeyboardButton("🎬 Video", callback_data=f"{URL_ACTION_PREFIX}video"),
        ]]
        await msg.reply_text(
            "🔗 Detecté una URL. ¿Qué quieres descargar?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def on_url_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user or context.user_data is None:
        return
    if not isinstance(query.message, Message):
        return
    await query.answer()

    kind = (query.data or "").removeprefix(URL_ACTION_PREFIX)
    if kind not in ("audio", "video"):
        return

    url = context.user_data.pop("url_pending", None)
    if not url:
        await query.edit_message_text("La URL expiró. Envía el enlace de nuevo.")
        return

    chat_id = query.message.chat_id if query.message else update.effective_user.id
    fmt = context.user_data.get("audio_format", "mp3")
    job = await queue_from(context).enqueue(
        context.application,
        kind=kind,
        url=url,
        chat_id=chat_id,
        user_id=update.effective_user.id,
        audio_format=fmt,
    )
    emoji = "🎵" if kind == "audio" else "🎬"
    await query.edit_message_text(
        f"{emoji} Trabajo en cola: #{job.id}. Usa /jobs para ver estado."
    )


def register(application: Application) -> None:
    # Sólo texto sin comando que contenga una URL
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://"),
            on_url_message,
        )
    )
    application.add_handler(
        CallbackQueryHandler(on_url_action, pattern=rf"^{URL_ACTION_PREFIX}(audio|video)$")
    )
