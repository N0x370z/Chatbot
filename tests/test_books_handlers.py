"""Handlers de libros: búsqueda con respaldo, selector de fuente y descarga."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import InlineKeyboardMarkup, Message, Update

from bot.handlers import books
from bot.services.base import BookResult, BooksApiError
from bot.services.sources import SOURCES, BookSource
from bot.state import BotStats, RateLimiter
from tests.conftest import EPUB, make_settings


def _buttons(markup: InlineKeyboardMarkup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def _context(args=None, user_data=None) -> MagicMock:
    ctx = MagicMock()
    ctx.args = args or []
    ctx.user_data = user_data if user_data is not None else {}
    db = MagicMock(get_file_id=AsyncMock(return_value=None), set_file_id=AsyncMock())
    ctx.application.bot_data = {
        "stats": BotStats(),
        "limiter": RateLimiter(window_seconds=60, max_requests=10),
        "settings": make_settings(),
        "http_session": MagicMock(closed=False),
        "book_search_cache": None,
        "db": db,
    }
    return ctx


def _command_update() -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=42)
    update.effective_message = AsyncMock()
    update.effective_message.reply_html.return_value = AsyncMock()  # mensaje de estado
    return update


def _callback_update(data: str) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=42)
    query = MagicMock(data=data, answer=AsyncMock(), edit_message_text=AsyncMock(),
                      edit_message_reply_markup=AsyncMock())
    query.message = MagicMock(spec=Message)
    for name in ("reply_document", "reply_text", "reply_html"):
        setattr(query.message, name, AsyncMock())
    update.callback_query = query
    return update


@pytest.fixture
def fake_sources(monkeypatch):
    """Sustituye el registro: cada fuente devuelve lo indicado en ``found``."""
    found: dict[str, list[BookResult] | Exception] = {}
    downloads = AsyncMock(return_value=(EPUB, "libro.epub"))

    def make(key):
        async def search(session, q, limit, settings):
            result = found.get(key, [])
            if isinstance(result, Exception):
                raise result
            return result
        return BookSource(key, SOURCES[key].label, "", search, downloads, "q")

    monkeypatch.setattr(books, "SOURCES", {key: make(key) for key in SOURCES})
    return found, downloads


def test_libro_uses_default_source(fake_sources):
    found, _ = fake_sources
    found["open_library"] = [BookResult("/works/OL1W", "Don Quijote")]
    update, ctx = _command_update(), _context(args=["quijote"])

    asyncio.run(books.cmd_libro(update, ctx))

    assert ctx.user_data["books_pending"] == [{"id": "/works/OL1W", "title": "Don Quijote", "source": "open_library"}]
    status = update.effective_message.reply_html.return_value
    text = status.edit_text.call_args[0][0]
    assert "Open Library" in text
    assert books.OTHER_SOURCES_CB in _buttons(status.edit_text.call_args.kwargs["reply_markup"])


def test_libro_falls_back_by_priority(fake_sources):
    found, _ = fake_sources
    found["open_library"] = BooksApiError("caída")
    found["libgen"] = [BookResult("l", "De libgen")]
    found["dbooks"] = [BookResult("d", "De dbooks")]  # dbooks tiene más prioridad
    update, ctx = _command_update(), _context(args=["python"])

    asyncio.run(books.cmd_libro(update, ctx))

    assert ctx.user_data["books_results_source"] == "dbooks"
    text = update.effective_message.reply_html.return_value.edit_text.call_args[0][0]
    assert "Open Library no dio resultados" in text


def test_libro_no_results_anywhere(fake_sources):
    update, ctx = _command_update(), _context(args=["zzz"])
    asyncio.run(books.cmd_libro(update, ctx))
    status = update.effective_message.reply_html.return_value
    assert "Ninguna fuente" in status.edit_text.call_args[0][0]


def test_retry_in_other_source(fake_sources):
    found, _ = fake_sources
    found["libgen"] = [BookResult("l", "De libgen")]
    update = _callback_update("bretry:libgen")
    ctx = _context(user_data={"books_query": "python", "books_results_source": "open_library"})

    asyncio.run(books.on_retry_source(update, ctx))

    assert ctx.user_data["books_pending"][0]["source"] == "libgen"
    assert "Libgen" in update.callback_query.edit_message_text.call_args[0][0]


def test_fuente_shows_picker_and_saves_choice():
    update, ctx = _command_update(), _context()
    asyncio.run(books.cmd_fuente(update, ctx))
    text = update.effective_message.reply_html.call_args[0][0]
    markup = update.effective_message.reply_html.call_args.kwargs["reply_markup"]
    assert "Actual: <b>Open Library</b>" in text
    assert "bsrc:libgen" in _buttons(markup)

    pick = _callback_update("bsrc:libgen")
    asyncio.run(books.on_source_pick(pick, ctx))
    assert ctx.user_data["book_source"] == "libgen"


def test_pick_downloads_and_keeps_results(fake_sources):
    _, downloads = fake_sources
    pending = [{"id": "/works/OL1W", "title": "Don Quijote", "source": "open_library"}]
    update, ctx = _callback_update("book:0"), _context(user_data={"books_pending": pending})

    asyncio.run(books.on_book_pick(update, ctx))

    assert downloads.call_args[0][1] == "/works/OL1W"
    update.callback_query.message.reply_document.assert_awaited_once()
    assert ctx.user_data["books_pending"] == pending


def test_pick_error_is_reported(fake_sources):
    _, downloads = fake_sources
    downloads.side_effect = BooksApiError("No disponible.")
    pending = [{"id": "x", "title": "Libro", "source": "internet_archive"}]
    update, ctx = _callback_update("book:0"), _context(user_data={"books_pending": pending})

    asyncio.run(books.on_book_pick(update, ctx))

    update.callback_query.message.reply_document.assert_not_awaited()
    assert "No disponible." in update.callback_query.message.reply_text.call_args[0][0]


def _convert_context(tmp_path, user_data):
    ctx = _context(args=["epub"], user_data=user_data)
    ctx.application.bot_data["settings"] = make_settings(download_path=tmp_path)
    return ctx


def _fake_convert(monkeypatch, seen: list):
    async def convert(path, fmt):
        seen.append(path)
        out = path.with_suffix(f".{fmt}")
        out.write_bytes(b"PK\x03\x04converted")
        return out
    monkeypatch.setattr("bot.utils.converter.convert_book", convert)


def test_convertir_redownloads_when_worker_moved_the_file(tmp_path, monkeypatch):
    """El worker ya movió el archivo a processed: se descarga de nuevo por file_id."""
    seen: list = []
    _fake_convert(monkeypatch, seen)
    tg_file = MagicMock()
    tg_file.download_to_drive = AsyncMock(side_effect=lambda custom_path: Path(custom_path).write_bytes(b"%PDF"))
    update = _command_update()
    ctx = _convert_context(tmp_path, {
        "last_uploaded_file": str(tmp_path / "incoming" / "libro.pdf"),  # ya no existe
        "last_uploaded_file_id": "FILE123",
    })
    ctx.bot.get_file = AsyncMock(return_value=tg_file)

    asyncio.run(books.cmd_convertir(update, ctx))

    ctx.bot.get_file.assert_awaited_once_with("FILE123")
    update.effective_message.reply_document.assert_awaited_once()
    assert seen[0].parent.name.startswith("convert_")  # carpeta privada, no incoming
    assert not seen[0].parent.exists()  # y se limpia al terminar


def test_convertir_without_upload():
    update, ctx = _command_update(), _context(args=["epub"])
    asyncio.run(books.cmd_convertir(update, ctx))
    assert "Envía un PDF o EPUB" in update.effective_message.reply_text.call_args[0][0]
