"""Tests para bot/handlers/url_detect.py."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram import Message, Update

from bot.handlers.url_detect import (
    URL_ACTION_PREFIX,
    _extract_url,
    _is_audio_domain,
    on_url_action,
    on_url_message,
)
from bot.state import BotStats, RateLimiter

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = {}
    stats = BotStats()
    limiter = RateLimiter(window_seconds=60, max_requests=10)
    app = MagicMock()
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock(return_value=MagicMock(id="ab12cd34"))
    app.bot_data = {"stats": stats, "limiter": limiter, "download_queue": mock_queue}
    ctx.application = app
    return ctx


def _make_update(user_id: int = 42, chat_id: int = 1000, text: str = "") -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    update.effective_message.text = text
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    return update


# ── _extract_url ─────────────────────────────────────────────────────────────

def test_extract_url_found():
    assert _extract_url("Mira esto https://youtu.be/abc123") == "https://youtu.be/abc123"


def test_extract_url_strips_trailing_punctuation():
    url = _extract_url("visita https://example.com.")
    assert url == "https://example.com"


def test_extract_url_none_when_absent():
    assert _extract_url("Hola como estás") is None


def test_extract_url_http():
    assert _extract_url("http://example.com/page") == "http://example.com/page"


# ── _is_audio_domain ─────────────────────────────────────────────────────────

def test_is_audio_domain_soundcloud():
    assert _is_audio_domain("https://soundcloud.com/artist/track") is True


def test_is_audio_domain_bandcamp():
    assert _is_audio_domain("https://artist.bandcamp.com/track/song") is True


def test_is_audio_domain_youtube_video_is_false():
    # Plain youtube.com is NOT in _AUDIO_DOMAINS (only music.youtube.com is)
    assert _is_audio_domain("https://www.youtube.com/watch?v=abc") is False


def test_is_audio_domain_music_youtube():
    assert _is_audio_domain("https://music.youtube.com/watch?v=xyz") is True


# ── on_url_message ───────────────────────────────────────────────────────────

def test_on_url_message_no_url():
    """Mensajes sin URL no hacen nada."""
    update = _make_update(text="Hola sin url")
    ctx = _make_context()
    asyncio.run(on_url_message(update, ctx))
    update.effective_message.reply_text.assert_not_called()


def test_on_url_message_audio_domain_auto_enqueues():
    """URL de SoundCloud se encola automáticamente como audio."""
    url = "https://soundcloud.com/artist/song"
    update = _make_update(text=url)
    ctx = _make_context()
    asyncio.run(on_url_message(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_called_once()
    kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert kwargs["kind"] == "audio"
    assert kwargs["url"] == url


def test_on_url_message_unknown_domain_shows_buttons():
    """URL de YouTube muestra botones de elección."""
    update = _make_update(text="https://youtu.be/dQw4w9WgXcQ")
    ctx = _make_context()
    asyncio.run(on_url_message(update, ctx))
    # No enqueue yet
    ctx.application.bot_data["download_queue"].enqueue.assert_not_called()
    # Shows inline keyboard
    update.effective_message.reply_text.assert_called_once()
    call_kwargs = update.effective_message.reply_text.call_args[1]
    assert "reply_markup" in call_kwargs


def test_on_url_message_rate_limited():
    """Rate limit exhausto → mensaje de error, sin enqueue."""
    update = _make_update(text="https://youtu.be/abc")
    ctx = _make_context()
    limiter: RateLimiter = ctx.application.bot_data["limiter"]
    for _ in range(10):
        limiter.allow(42)
    asyncio.run(on_url_message(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_not_called()
    update.effective_message.reply_text.assert_called_once()


def test_on_url_message_stores_url_in_user_data():
    """La URL se almacena en user_data para el callback."""
    url = "https://youtu.be/dQw4w9WgXcQ"
    update = _make_update(text=url)
    ctx = _make_context()
    asyncio.run(on_url_message(update, ctx))
    assert ctx.user_data.get("url_pending") == url


# ── on_url_action ────────────────────────────────────────────────────────────

def test_on_url_action_audio():
    """Botón Audio encola job kind=audio."""
    update = _make_update()
    ctx = _make_context()
    ctx.user_data["url_pending"] = "https://youtu.be/test"

    query = AsyncMock()
    query.data = f"{URL_ACTION_PREFIX}audio"
    query.message = MagicMock(spec=Message)
    query.message.chat_id = 1000
    update.callback_query = query

    asyncio.run(on_url_action(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_called_once()
    kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert kwargs["kind"] == "audio"
    assert "url_pending" not in ctx.user_data  # limpiada


def test_on_url_action_video():
    """Botón Video encola job kind=video."""
    update = _make_update()
    ctx = _make_context()
    ctx.user_data["url_pending"] = "https://youtu.be/test"

    query = AsyncMock()
    query.data = f"{URL_ACTION_PREFIX}video"
    query.message = MagicMock(spec=Message)
    query.message.chat_id = 1000
    update.callback_query = query

    asyncio.run(on_url_action(update, ctx))
    kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert kwargs["kind"] == "video"


def test_on_url_action_expired_url():
    """Sin url_pending → mensaje de error, sin enqueue."""
    update = _make_update()
    ctx = _make_context()
    # No url_pending in user_data

    query = AsyncMock()
    query.data = f"{URL_ACTION_PREFIX}video"
    query.message = MagicMock(spec=Message)
    update.callback_query = query

    asyncio.run(on_url_action(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_not_called()
    query.edit_message_text.assert_called_once()
