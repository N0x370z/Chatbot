"""Tests de integración de Gutenberg."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from bot.services.books_api import BooksApiError
from bot.services.gutenberg import search_gutenberg


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


def test_search_gutenberg_parses_results() -> None:
    payload = {
        "results": [
            {
                "id": 123,
                "title": "Test Book",
                "authors": [{"name": "Ana Autor"}],
            },
            {
                "id": 124,
                "title": "Another Book",
                "authors": [{"name": "Bob Autor"}],
            }
        ]
    }
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_gutenberg(session, "test", 5))
    assert len(results) == 2
    assert results[0].id == "123"
    assert results[0].title == "Test Book - Ana Autor"


def test_search_gutenberg_empty() -> None:
    session = DummySession([DummyResponse({"results": []})])
    results = asyncio.run(search_gutenberg(session, "test", 5))
    assert results == []


def test_search_gutenberg_timeout() -> None:
    session = DummySession([TimeoutError(), TimeoutError(), TimeoutError()])
    with pytest.raises(BooksApiError, match="Gutenberg tardó demasiado en responder."):
        asyncio.run(search_gutenberg(session, "test", 5))


def test_search_gutenberg_malformed_json() -> None:
    session = DummySession([DummyResponse(ValueError("Bad JSON"))])
    with pytest.raises(BooksApiError, match="Gutenberg devolvió JSON inválido."):
        asyncio.run(search_gutenberg(session, "test", 5))


def test_search_gutenberg_4xx() -> None:
    session = DummySession([DummyResponse(None, status=404)])
    with pytest.raises(BooksApiError, match="No se pudo contactar Gutenberg."):
        asyncio.run(search_gutenberg(session, "test", 5))
