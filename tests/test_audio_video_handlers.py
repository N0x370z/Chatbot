"""Tests for bot/handlers/audio.py and bot/handlers/video.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram import Update

from bot.handlers.audio import (
    AUDIO_FMT_PREFIX,
    cmd_apple,
    cmd_audio,
    cmd_formato_audio,
    on_audio_fmt_pick,
)
from bot.handlers.video import cmd_video
from bot.state import BotStats, RateLimiter

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_context(url: str | None = None, fmt: str = "mp3") -> MagicMock:
    """Return a minimal mock context."""
    ctx = MagicMock()
    ctx.args = [url] if url else []
    ctx.user_data = {"audio_format": fmt}

    stats = BotStats()
    limiter = RateLimiter(window_seconds=60, max_requests=10)

    app = MagicMock()
    app.bot_data = {
        "stats": stats,
        "limiter": limiter,
        "download_queue": AsyncMock(),
    }
    app.bot_data["download_queue"].enqueue = AsyncMock(
        return_value=MagicMock(id="aabbccdd")
    )
    ctx.application = app
    return ctx


def _make_update(user_id: int = 42, chat_id: int = 1000) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    return update


# ──────────────────────────────────────────────────────────────────────────────
# cmd_audio
# ──────────────────────────────────────────────────────────────────────────────

def test_cmd_audio_no_url():
    """Without a URL, the command shows usage instructions."""
    update = _make_update()
    ctx = _make_context(url=None)
    asyncio.run(cmd_audio(update, ctx))
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "/audio" in msg


def test_cmd_audio_enqueues_job():
    """Valid URL enqueues an audio job."""
    update = _make_update()
    ctx = _make_context(url="https://youtu.be/test")
    asyncio.run(cmd_audio(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_called_once()
    call_kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert call_kwargs["kind"] == "audio"
    assert call_kwargs["url"] == "https://youtu.be/test"


def test_cmd_audio_rate_limited():
    """When rate limit is exhausted, the command rejects the request."""
    update = _make_update()
    ctx = _make_context(url="https://youtu.be/test")
    # Exhaust the limiter for user 42
    limiter: RateLimiter = ctx.application.bot_data["limiter"]
    for _ in range(10):
        limiter.allow(42)

    asyncio.run(cmd_audio(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_not_called()
    update.effective_message.reply_text.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# cmd_apple
# ──────────────────────────────────────────────────────────────────────────────

def test_cmd_apple_no_url():
    update = _make_update()
    ctx = _make_context(url=None)
    asyncio.run(cmd_apple(update, ctx))
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "/apple" in msg


def test_cmd_apple_enqueues_job():
    update = _make_update()
    ctx = _make_context(url="https://youtu.be/test")
    asyncio.run(cmd_apple(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_called_once()
    call_kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert call_kwargs["kind"] == "apple"


# ──────────────────────────────────────────────────────────────────────────────
# cmd_video
# ──────────────────────────────────────────────────────────────────────────────

def test_cmd_video_no_url():
    update = _make_update()
    ctx = _make_context(url=None)
    asyncio.run(cmd_video(update, ctx))
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "/video" in msg


def test_cmd_video_enqueues_job():
    update = _make_update()
    ctx = _make_context(url="https://youtu.be/test")
    asyncio.run(cmd_video(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_called_once()
    call_kwargs = ctx.application.bot_data["download_queue"].enqueue.call_args[1]
    assert call_kwargs["kind"] == "video"


def test_cmd_video_rate_limited():
    update = _make_update()
    ctx = _make_context(url="https://youtu.be/test")
    limiter: RateLimiter = ctx.application.bot_data["limiter"]
    for _ in range(10):
        limiter.allow(42)

    asyncio.run(cmd_video(update, ctx))
    ctx.application.bot_data["download_queue"].enqueue.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# cmd_formato_audio
# ──────────────────────────────────────────────────────────────────────────────

def test_cmd_formato_audio_shows_current_format():
    update = _make_update()
    ctx = _make_context(fmt="opus")
    asyncio.run(cmd_formato_audio(update, ctx))
    update.effective_message.reply_html.assert_called_once()
    html = update.effective_message.reply_html.call_args[0][0]
    assert "OPUS" in html


# ──────────────────────────────────────────────────────────────────────────────
# on_audio_fmt_pick
# ──────────────────────────────────────────────────────────────────────────────

def test_on_audio_fmt_pick_valid():
    update = _make_update()
    ctx = _make_context()
    query = AsyncMock()
    query.data = f"{AUDIO_FMT_PREFIX}flac"
    update.callback_query = query

    asyncio.run(on_audio_fmt_pick(update, ctx))
    assert ctx.user_data["audio_format"] == "flac"
    query.edit_message_text.assert_called_once()
    assert "FLAC" in query.edit_message_text.call_args[0][0]


def test_on_audio_fmt_pick_invalid():
    update = _make_update()
    ctx = _make_context()
    query = AsyncMock()
    query.data = f"{AUDIO_FMT_PREFIX}invalid_fmt"
    update.callback_query = query

    asyncio.run(on_audio_fmt_pick(update, ctx))
    # Should not update user_data or send any message
    assert ctx.user_data.get("audio_format") == "mp3"  # unchanged
    query.edit_message_text.assert_not_called()
