"""Tests de integración de Open Library."""

from __future__ import annotations

import asyncio
import pytest
import aiohttp
from bot.services.books_api import BooksApiError
from bot.services.open_library import search_open_library


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
    session = DummySession([asyncio.TimeoutError(), asyncio.TimeoutError(), asyncio.TimeoutError()])
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
