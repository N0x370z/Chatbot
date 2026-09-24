"""Tests de integración de Open Library."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from bot.services.books_api import BooksApiError
from bot.services.open_library import download_open_library, search_open_library


class DummyResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            from unittest.mock import Mock
            req_info = Mock()
            req_info.real_url = "http://dummy"
            raise aiohttp.ClientResponseError(req_info, (), status=self.status)

    async def json(self, content_type=None):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def get(self, url, **kwargs):
        resp = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_search_open_library_parses_results() -> None:
    payload = {
        "docs": [
            {
                "key": "OL123M",
                "title": "Test OL Book",
                "author_name": ["Ana OL"],
            },
            {
                "key": "OL124M",
                "title": "Another OL Book",
                "author_name": ["Bob OL"],
            }
        ]
    }
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_open_library(session, "test", 5))
    assert len(results) == 2
    assert results[0].id == "OL123M"
    assert results[0].title == "Test OL Book - Ana OL"


def test_search_open_library_empty() -> None:
    session = DummySession([DummyResponse({"docs": []})])
    results = asyncio.run(search_open_library(session, "test", 5))
    assert results == []


def test_search_open_library_timeout() -> None:
    session = DummySession([TimeoutError(), TimeoutError(), TimeoutError()])
    with pytest.raises(BooksApiError, match="Open Library tardó demasiado."):
        asyncio.run(search_open_library(session, "test", 5))


def test_search_open_library_malformed_json() -> None:
    session = DummySession([DummyResponse(ValueError("Bad JSON"))])
    with pytest.raises(BooksApiError, match="Open Library devolvió JSON inválido."):
        asyncio.run(search_open_library(session, "test", 5))


def test_search_open_library_4xx() -> None:
    session = DummySession([DummyResponse(None, status=404)])
    with pytest.raises(BooksApiError, match="No se pudo contactar Open Library."):
        asyncio.run(search_open_library(session, "test", 5))


def test_search_open_library_filters_public_ebooks() -> None:
    captured = {}

    class CapturingSession(DummySession):
        async def get(self, url, **kwargs):
            captured["url"] = url
            return await super().get(url, **kwargs)

    session = CapturingSession([DummyResponse({"docs": []})])
    asyncio.run(search_open_library(session, "quijote", 5))
    assert "ebook_access%3Apublic" in captured["url"]


class _IASearchResponse(DummyResponse):
    """Respuesta usable con ``async with session.get(...)``."""


class _CtxSession:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, **kwargs):
        return self.responses.pop(0)


class _Settings:
    max_file_size_bytes = 50 * 1024 * 1024


def test_download_open_library_tries_ia_copies(monkeypatch) -> None:
    payload = {"response": {"docs": [{"identifier": "bad"}, {"identifier": "good"}]}}
    session = _CtxSession([_IASearchResponse(payload)])
    tried = []

    async def fake_ia(sess, identifier, settings):
        tried.append(identifier)
        if identifier == "bad":
            raise BooksApiError("sin archivo")
        return b"PK\x03\x04", "libro.epub"

    monkeypatch.setattr("bot.services.open_library.download_internet_archive", fake_ia)
    data, name = asyncio.run(download_open_library(session, "/works/OL503666W", _Settings()))
    assert tried == ["bad", "good"]
    assert name == "libro.epub"


def test_download_open_library_no_public_copy() -> None:
    session = _CtxSession([_IASearchResponse({"response": {"docs": []}})])
    with pytest.raises(BooksApiError, match="no tiene una copia de descarga libre"):
        asyncio.run(download_open_library(session, "/works/OL1W", _Settings()))


def test_download_open_library_invalid_id() -> None:
    with pytest.raises(BooksApiError, match="ID de Open Library inválido"):
        asyncio.run(download_open_library(_CtxSession([]), "garbage", _Settings()))
