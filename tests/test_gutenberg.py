"""Tests de integración de Gutenberg."""

from __future__ import annotations

import asyncio

from bot.services.gutenberg import search_gutenberg


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return self._payload


class DummySession:
    def __init__(self, payload):
        self._payload = payload

    def get(self, url, **kwargs):
        return DummyResponse(self._payload)


def test_search_gutenberg_parses_results() -> None:
    payload = {
        "results": [
            {
                "id": 123,
                "title": "Test Book",
                "authors": [{"name": "Ana Autor"}],
                "formats": {},
            }
        ]
    }
    session = DummySession(payload)
    results = asyncio.run(search_gutenberg(session, "test", 5))
    assert len(results) == 1
    assert results[0].id == "123"
    assert results[0].title == "Test Book - Ana Autor"
