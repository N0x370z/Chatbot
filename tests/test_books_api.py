"""Tests del parser de resultados de la API de libros."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import aiohttp
import pytest

from bot.config import Settings
from bot.services.books_api import (
    BookResult,
    BooksApiError,
    _full_request_url,
    _safe_filename,
    download_book_bytes,
    normalize_book_results,
    search_books,
)


class DummyResponse:
    def __init__(self, payload=None, status=200, headers=None, content_length=None, content=b""):
        self._payload = payload
        self.status = status
        self.headers = headers or {}
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


def test_normalize_book_results_results_key() -> None:
    payload = {
        "results": [
            {"id": "a1", "title": "Alpha"},
            {"book_id": "b2", "name": "Beta"},
        ],
    }
    got = normalize_book_results(payload, max_items=10)
    assert got == [
        BookResult(id="a1", title="Alpha"),
        BookResult(id="b2", title="Beta"),
    ]


def test_normalize_book_results_respects_max() -> None:
    payload = {"items": [{"id": str(i), "title": f"T{i}"} for i in range(20)]}
    got = normalize_book_results(payload, max_items=3)
    assert len(got) == 3
    assert got[0].id == "0"


def test_safe_filename() -> None:
    assert _safe_filename("Normal Book") == "Normal_Book"
    assert _safe_filename("  With Spaces!  ") == "With_Spaces_"
    assert _safe_filename("") == "libro"
    assert _safe_filename("!@#$%^") == "_"


from pathlib import Path


def _dummy_settings(books_api_base_url="http://api.example.com", max_file_size_mb=50) -> Settings:
    return Settings(
        telegram_bot_token="123",
        admin_user_id=1,
        allowed_user_ids=frozenset(),
        max_file_size_mb=max_file_size_mb,
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
        books_api_max_results=5,
        incoming_files_path=Path("/tmp/incoming"),
        max_upload_size_mb=50,
        calibre_library_path=None,
        ssl_verify=True,
    )


def test_full_request_url() -> None:
    s = _dummy_settings(books_api_base_url="http://api.example.com/")
    assert _full_request_url(s, "/search") == "http://api.example.com/search"
    assert _full_request_url(s, "http://other.com/path") == "http://other.com/path"


def test_search_books_success() -> None:
    s = _dummy_settings()
    payload = {"results": [{"id": "1", "title": "Test Book"}]}
    session = DummySession([DummyResponse(payload)])

    results = asyncio.run(search_books(session, s, "query"))
    assert len(results) == 1
    assert results[0].id == "1"


def test_search_books_no_base_url() -> None:
    s = _dummy_settings(books_api_base_url="")
    session = DummySession([])
    with pytest.raises(BooksApiError, match="BOOKS_API_BASE_URL no está configurada."):
        asyncio.run(search_books(session, s, "query"))


def test_search_books_http_error() -> None:
    s = _dummy_settings()
    session = DummySession([DummyResponse(status=500)])
    with pytest.raises(BooksApiError, match="La API respondió con error HTTP 500"):
        asyncio.run(search_books(session, s, "query"))


def test_search_books_client_error() -> None:
    s = _dummy_settings()
    session = DummySession([aiohttp.ClientError("Network Error")])
    with pytest.raises(BooksApiError, match="No se pudo contactar la API de libros."):
        asyncio.run(search_books(session, s, "query"))


def test_search_books_bad_json() -> None:
    s = _dummy_settings()
    session = DummySession([DummyResponse(ValueError("Bad JSON"))])
    with pytest.raises(BooksApiError, match="La API no devolvió JSON válido."):
        asyncio.run(search_books(session, s, "query"))


def test_download_book_bytes_success() -> None:
    s = _dummy_settings()
    headers = {"Content-Disposition": 'attachment; filename="test.pdf"'}
    session = DummySession([DummyResponse(content=b"hello", headers=headers, content_length=5)])

    data, filename = asyncio.run(download_book_bytes(session, s, "1"))
    assert data == b"hello"
    assert filename == "test.pdf"


def test_download_book_bytes_no_base_url() -> None:
    s = _dummy_settings(books_api_base_url="")
    session = DummySession([])
    with pytest.raises(BooksApiError, match="BOOKS_API_BASE_URL no está configurada."):
        asyncio.run(download_book_bytes(session, s, "1"))


def test_download_book_bytes_too_large_content_length() -> None:
    s = _dummy_settings(max_file_size_mb=1)
    session = DummySession([DummyResponse(content_length=5 * 1024 * 1024)])
    with pytest.raises(BooksApiError, match="El archivo remoto \\(~5 MB\\) supera el límite."):
        asyncio.run(download_book_bytes(session, s, "1"))


def test_download_book_bytes_too_large_download() -> None:
    s = _dummy_settings(max_file_size_mb=1) # 1 MB limit
    session = DummySession([DummyResponse(content=b"x" * (2 * 1024 * 1024), content_length=None)])
    with pytest.raises(BooksApiError, match="El archivo descargado supera MAX_FILE_SIZE_MB."):
        asyncio.run(download_book_bytes(session, s, "1"))


def test_download_book_bytes_fallback_filename() -> None:
    s = _dummy_settings()
    headers = {"Content-Type": "application/epub+zip"}
    session = DummySession([DummyResponse(content=b"epub_data", headers=headers)])

    data, filename = asyncio.run(download_book_bytes(session, s, "mybook"))
    assert data == b"epub_data"
    assert filename == "mybook.epub"


def test_download_book_bytes_http_error() -> None:
    s = _dummy_settings()
    session = DummySession([DummyResponse(status=403)])
    with pytest.raises(BooksApiError, match="Descarga rechazada por la API \\(HTTP 403\\)."):
        asyncio.run(download_book_bytes(session, s, "1"))

def test_download_book_bytes_client_error() -> None:
    s = _dummy_settings()
    session = DummySession([aiohttp.ClientError("Network Error")])
    with pytest.raises(BooksApiError, match="No se pudo descargar el libro."):
        asyncio.run(download_book_bytes(session, s, "1"))
