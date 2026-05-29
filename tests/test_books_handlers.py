"""Tests for the new default book source in book handlers."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update

from bot.config import Settings
from bot.handlers.books import cmd_fuente, cmd_libro
from bot.services.books_api import BookResult
from bot.state import BotStats, RateLimiter


def make_settings(books_api_base_url: str = "") -> Settings:
    return Settings(
        telegram_bot_token="test_token",
        admin_user_id=123,
        allowed_user_ids=frozenset(),
        max_file_size_mb=50,
        download_path=Path("/tmp"),
        log_level="INFO",
        rate_limit_window_sec=60,
        rate_limit_max_requests=10,
        books_api_base_url=books_api_base_url,
        books_api_key="",
        books_api_key_header="Authorization",
        books_api_key_prefix="Bearer",
        books_api_search_path="/search",
        books_api_download_path_template="/download/{id}",
        books_api_query_param="q",
        books_api_timeout_sec=60,
        books_api_max_results=8,
        incoming_files_path=Path("/tmp"),
        max_upload_size_mb=50,
        calibre_library_path=None,
        ssl_verify=True,
    )


def _make_context(args: list[str] | None = None, api_url: str = "") -> MagicMock:
    ctx = MagicMock()
    ctx.args = args or []
    ctx.user_data = {}

    stats = BotStats()
    limiter = RateLimiter(window_seconds=60, max_requests=10)
    settings = make_settings(books_api_base_url=api_url)

    http_session = MagicMock()
    http_session.closed = False

    app = MagicMock()
    app.bot_data = {
        "stats": stats,
        "limiter": limiter,
        "settings": settings,
        "http_session": http_session,
        "book_search_cache": None,
    }
    ctx.application = app
    return ctx


def _make_update(user_id: int = 42) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = AsyncMock()
    return update


def test_cmd_fuente_default_standard_ebooks() -> None:
    """Verifies that cmd_fuente shows standard_ebooks as the default when not configured."""
    update = _make_update()
    ctx = _make_context()

    asyncio.run(cmd_fuente(update, ctx))

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Fuente actual: Standard Ebooks" in msg


def test_cmd_libro_default_standard_ebooks() -> None:
    """Verifies that cmd_libro searches standard_ebooks as the default when not configured."""
    update = _make_update()
    ctx = _make_context(args=["el", "quijote"])

    mock_results = [BookResult(id="1", title="Don Quijote")]

    async def mock_search_func(*args, **kwargs):
        return mock_results

    with patch("bot.handlers.books.search_standard_ebooks", side_effect=mock_search_func) as mock_search:
        asyncio.run(cmd_libro(update, ctx))

        mock_search.assert_called_once()
        assert ctx.user_data["books_pending"] == [
            {"id": "1", "title": "Don Quijote", "source": "standard_ebooks"}
        ]
        update.effective_message.reply_html.assert_called_once()
        reply_markup = update.effective_message.reply_html.call_kwargs.get("reply_markup")
        assert reply_markup is not None
