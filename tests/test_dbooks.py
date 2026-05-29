"""Tests for dbooks."""

import asyncio
from unittest.mock import Mock

import aiohttp
import pytest

from bot.services.dbooks import BooksApiError, download_dbooks, search_dbooks


class DummyResponse:
    def __init__(self, payload=None, status=200, content_length=None, content=b""):
        self._payload = payload
        self.status = status
        self.content_length = content_length
        self._content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            req_info = Mock()
            req_info.real_url = "http://dummy"
            raise aiohttp.ClientResponseError(req_info, (), status=self.status)

    async def json(self, content_type=None):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def read(self):
        if isinstance(self._content, Exception):
            raise self._content
        return self._content


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def get(self, url, **kwargs):
        resp = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_search_dbooks_success():
    payload = {
        "status": "ok",
        "books": [
            {"id": "1", "title": "Linux", "authors": "Linus"}
        ]
    }
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_dbooks(session, "linux", 5))
    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].title == "Linux - Linus"


def test_search_dbooks_timeout():
    session = DummySession([TimeoutError()])
    with pytest.raises(BooksApiError, match="dBooks tardó demasiado en responder."):
        asyncio.run(search_dbooks(session, "linux", 5))


def test_search_dbooks_bad_json():
    session = DummySession([DummyResponse(ValueError())])
    with pytest.raises(BooksApiError, match="dBooks devolvió datos inválidos."):
        asyncio.run(search_dbooks(session, "linux", 5))


class MockSettings:
    max_file_size_bytes = 1024 * 1024 * 50


def test_download_dbooks_success():
    meta_payload = {"status": "ok", "download": "http://dl", "title": "Linux"}
    session = DummySession([
        DummyResponse(meta_payload),
        DummyResponse(content=b"%PDF_data", content_length=9)
    ])
    data, filename = asyncio.run(download_dbooks(session, "1", MockSettings()))
    assert data == b"%PDF_data"
    assert filename == "Linux.pdf"


def test_download_dbooks_no_download_link():
    meta_payload = {"status": "ok", "title": "Linux"} # no download
    session = DummySession([DummyResponse(meta_payload)])
    with pytest.raises(BooksApiError, match="No se encontró un link de descarga directo en dBooks."):
        asyncio.run(download_dbooks(session, "1", MockSettings()))


def test_download_dbooks_too_large():
    meta_payload = {"status": "ok", "download": "http://dl", "title": "Linux"}
    settings = MockSettings()
    settings.max_file_size_bytes = 100
    session = DummySession([
        DummyResponse(meta_payload),
        DummyResponse(content_length=150)
    ])
    with pytest.raises(BooksApiError, match="El archivo \\(~0 MB\\) supera el límite."):
        asyncio.run(download_dbooks(session, "1", settings))
