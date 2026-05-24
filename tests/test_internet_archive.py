"""Tests for Internet Archive service."""

import asyncio
from unittest.mock import Mock

import aiohttp
import pytest

from bot.services.internet_archive import (
    BooksApiError,
    _safe_filename,
    download_internet_archive,
    search_internet_archive,
)


class DummyResponse:
    def __init__(self, payload=None, status=200, content_length=None, content=b""):
        self._payload = payload
        self.status = status
        self.content_length = content_length
        self._content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
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


class MockSettings:
    max_file_size_bytes = 50 * 1024 * 1024


# ---------- _safe_filename ----------

def test_ia_safe_filename_normal():
    assert _safe_filename("My Book") == "My_Book"

def test_ia_safe_filename_empty():
    assert _safe_filename("") == "libro"


# ---------- search ----------

def test_search_internet_archive_success():
    payload = {
        "response": {
            "docs": [
                {"identifier": "id123", "title": "Linux Basics", "creator": "Alice"},
                {"identifier": "id456", "title": "Python 101"},
            ]
        }
    }
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_internet_archive(session, "linux", 5))
    assert len(results) == 2
    assert results[0].id == "id123"
    assert results[0].title == "Linux Basics - Alice"
    assert results[1].title == "Python 101"


def test_search_internet_archive_empty_docs():
    payload = {"response": {"docs": []}}
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_internet_archive(session, "linux", 5))
    assert results == []


def test_search_internet_archive_bad_json():
    session = DummySession([DummyResponse(ValueError())])
    with pytest.raises(BooksApiError, match="Internet Archive devolvió datos inválidos."):
        asyncio.run(search_internet_archive(session, "linux", 5))


def test_search_internet_archive_timeout():
    session = DummySession([TimeoutError()])
    with pytest.raises(BooksApiError, match="Internet Archive tardó demasiado"):
        asyncio.run(search_internet_archive(session, "linux", 5))


def test_search_internet_archive_client_error():
    session = DummySession([aiohttp.ClientError("err")])
    with pytest.raises(BooksApiError, match="No se pudo contactar Internet Archive"):
        asyncio.run(search_internet_archive(session, "linux", 5))


def test_search_internet_archive_respects_max():
    docs = [{"identifier": f"id{i}", "title": f"Book {i}"} for i in range(10)]
    payload = {"response": {"docs": docs}}
    session = DummySession([DummyResponse(payload)])
    results = asyncio.run(search_internet_archive(session, "book", 3))
    assert len(results) == 3


# ---------- download ----------

def test_download_internet_archive_epub_preferred():
    meta = {
        "metadata": {"title": "My Book"},
        "files": [
            {"name": "book.epub", "format": "epub"},
            {"name": "book.pdf", "format": "PDF"},
        ]
    }
    session = DummySession([
        DummyResponse(meta),
        DummyResponse(content=b"PK\x03\x04bytes"),
    ])
    data, fname = asyncio.run(download_internet_archive(session, "myid", MockSettings()))
    assert data == b"PK\x03\x04bytes"
    assert fname.endswith(".epub")


def test_download_internet_archive_pdf_fallback():
    meta = {
        "metadata": {"title": "My Book"},
        "files": [
            {"name": "book.pdf", "format": "Text PDF"},
        ]
    }
    session = DummySession([
        DummyResponse(meta),
        DummyResponse(content=b"%PDF_bytes"),
    ])
    data, fname = asyncio.run(download_internet_archive(session, "myid", MockSettings()))
    assert data == b"%PDF_bytes"
    assert fname.endswith(".pdf")


def test_download_internet_archive_no_files_key():
    meta = {"metadata": {"title": "Empty"}}  # files key missing entirely
    session = DummySession([DummyResponse(meta)])
    with pytest.raises(BooksApiError, match="No se encontraron archivos"):
        asyncio.run(download_internet_archive(session, "myid", MockSettings()))


def test_download_internet_archive_empty_files_list():
    meta = {"metadata": {"title": "Empty"}, "files": []}
    session = DummySession([DummyResponse(meta)])
    with pytest.raises(BooksApiError, match="No se encontró un EPUB o PDF descargable"):
        asyncio.run(download_internet_archive(session, "myid", MockSettings()))


def test_download_internet_archive_no_supported_format():
    meta = {
        "metadata": {"title": "Weird"},
        "files": [{"name": "book.zip", "format": "ZIP"}],
    }
    session = DummySession([DummyResponse(meta)])
    with pytest.raises(BooksApiError, match="No se encontró un EPUB o PDF descargable"):
        asyncio.run(download_internet_archive(session, "myid", MockSettings()))


def test_download_internet_archive_too_large():
    meta = {
        "metadata": {"title": "Big"},
        "files": [{"name": "book.epub", "format": "epub"}],
    }
    settings = MockSettings()
    settings.max_file_size_bytes = 100
    session = DummySession([
        DummyResponse(meta),
        DummyResponse(content_length=5000),
    ])
    with pytest.raises(BooksApiError, match="supera el límite"):
        asyncio.run(download_internet_archive(session, "myid", settings))
