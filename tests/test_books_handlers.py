"""Tests for the new default book source in book handlers."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Message, Update

from bot.config import Settings
from bot.handlers.books import cmd_fuente, cmd_libro, on_book_pick
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


def test_cmd_fuente_default_open_library() -> None:
    """Verifies that cmd_fuente shows the real default (Open Library) when not configured."""
    update = _make_update()
    ctx = _make_context()

    asyncio.run(cmd_fuente(update, ctx))

    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Fuente actual: Open Library" in msg


def test_cmd_libro_default_open_library() -> None:
    """Verifies that cmd_libro searches open_library as the default when no API is configured."""
    update = _make_update()
    ctx = _make_context(args=["el", "quijote"])

    mock_results = [BookResult(id="1", title="Don Quijote")]

    async def mock_search_func(*args, **kwargs):
        return mock_results

    with patch("bot.handlers.books.search_open_library", side_effect=mock_search_func) as mock_search:
        asyncio.run(cmd_libro(update, ctx))

        mock_search.assert_called_once()
        assert ctx.user_data["books_pending"] == [
            {"id": "1", "title": "Don Quijote", "source": "open_library"}
        ]
        update.effective_message.reply_html.assert_called_once()
        reply_markup = update.effective_message.reply_html.call_kwargs.get("reply_markup")
        assert reply_markup is not None


def _make_pick_update(idx: int = 0) -> MagicMock:
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = f"book:{idx}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock(spec=Message)
    query.message.reply_document = AsyncMock()
    query.message.reply_text = AsyncMock()
    query.message.reply_html = AsyncMock()
    update.callback_query = query
    return update


def _make_pick_context(pending: list[dict]) -> MagicMock:
    ctx = _make_context()
    ctx.user_data = {"books_pending": pending}
    db = MagicMock()
    db.get_file_id = AsyncMock(return_value=None)
    db.set_file_id = AsyncMock()
    ctx.application.bot_data["db"] = db
    return ctx


def test_on_book_pick_downloads_open_library() -> None:
    """Open Library results must be downloaded (via IA), not rejected."""
    pending = [{"id": "/works/OL1W", "title": "Don Quijote", "source": "open_library"}]
    update = _make_pick_update()
    ctx = _make_pick_context(pending)

    download = AsyncMock(return_value=(b"PK\x03\x04data", "Don_Quijote.epub"))
    with patch.dict("bot.handlers.books.DOWNLOADERS", {"open_library": download}):
        asyncio.run(on_book_pick(update, ctx))

    download.assert_awaited_once()
    assert download.call_args[0][1] == "/works/OL1W"
    update.callback_query.message.reply_document.assert_awaited_once()
    # La lista se conserva para poder descargar otro resultado.
    assert ctx.user_data["books_pending"] == pending


def test_on_book_pick_error_keeps_results() -> None:
    """A failed download reports the error and keeps the results for another pick."""
    from bot.services.books_api import BooksApiError

    pending = [{"id": "x", "title": "Libro", "source": "internet_archive"}]
    update = _make_pick_update()
    ctx = _make_pick_context(pending)

    download = AsyncMock(side_effect=BooksApiError("No disponible."))
    with patch.dict("bot.handlers.books.DOWNLOADERS", {"internet_archive": download}):
        asyncio.run(on_book_pick(update, ctx))

    update.callback_query.message.reply_document.assert_not_awaited()
    msg = update.callback_query.message.reply_text.call_args[0][0]
    assert "No disponible." in msg
    assert ctx.user_data["books_pending"] == pending
