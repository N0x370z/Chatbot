"""Tests for Standard Ebooks service."""

import asyncio
from unittest.mock import Mock

import aiohttp
import pytest

from bot.services.standard_ebooks import (
    BooksApiError,
    _parse_opds,
    _safe_filename,
    download_standard_ebooks,
    search_standard_ebooks,
)

# Minimal OPDS XML feed
_VALID_OPDS = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Moby-Dick</title>
    <author><name>Herman Melville</name></author>
    <link type="application/epub+zip" href="https://standardebooks.org/ebooks/herman-melville_moby-dick/downloads/standard.epub"/>
  </entry>
  <entry>
    <title>Pride and Prejudice</title>
    <author><name>Jane Austen</name></author>
    <link type="application/epub+zip" href="https://standardebooks.org/ebooks/jane-austen_pride-and-prejudice/downloads/standard.epub"/>
  </entry>
  <entry>
    <title>No Download Book</title>
    <author><name>Unknown</name></author>
  </entry>
</feed>
"""

_EMPTY_OPDS = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""


class DummyResponse:
    def __init__(self, content=b"", status=200, content_length=None):
        self._content = content
        self.status = status
        self.content_length = content_length

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            req_info = Mock()
            req_info.real_url = "http://dummy"
            raise aiohttp.ClientResponseError(req_info, (), status=self.status)

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

def test_se_safe_filename():
    assert _safe_filename("My Book!") == "My_Book_"
    assert _safe_filename("") == "libro"


# ---------- _parse_opds ----------

def test_parse_opds_finds_entries():
    results = _parse_opds(_VALID_OPDS, "moby", 10)
    assert len(results) == 1
    assert results[0].title == "Moby-Dick - Herman Melville"
    assert "standard.epub" in results[0].id


def test_parse_opds_empty_feed():
    results = _parse_opds(_EMPTY_OPDS, "anything", 10)
    assert results == []


def test_parse_opds_respects_max():
    results = _parse_opds(_VALID_OPDS, "a", 1)
    assert len(results) == 1


def test_parse_opds_skips_entry_without_epub():
    results = _parse_opds(_VALID_OPDS, "no download", 10)
    assert results == []


def test_parse_opds_invalid_xml():
    with pytest.raises(BooksApiError, match="Standard Ebooks devolvió XML inválido"):
        _parse_opds(b"NOT XML!!!", "query", 5)


# ---------- search ----------

def test_search_standard_ebooks_success():
    session = DummySession([DummyResponse(_VALID_OPDS)])
    results = asyncio.run(search_standard_ebooks(session, "pride", 10))
    assert len(results) == 1
    assert "Austen" in results[0].title


def test_search_standard_ebooks_timeout():
    session = DummySession([TimeoutError()])
    with pytest.raises(BooksApiError, match="Standard Ebooks tardó demasiado"):
        asyncio.run(search_standard_ebooks(session, "moby", 5))


def test_search_standard_ebooks_client_error():
    session = DummySession([aiohttp.ClientError("err")])
    with pytest.raises(BooksApiError, match="No se pudo contactar Standard Ebooks"):
        asyncio.run(search_standard_ebooks(session, "moby", 5))


# ---------- download ----------

def test_download_standard_ebooks_success():
    url = "https://standardebooks.org/ebooks/standard.epub"
    session = DummySession([DummyResponse(b"PK\x03\x04content")])
    data, fname = asyncio.run(download_standard_ebooks(session, url, MockSettings()))
    assert data == b"PK\x03\x04content"
    assert fname == "standard.epub"


def test_download_standard_ebooks_too_large():
    url = "https://standardebooks.org/ebooks/huge.epub"
    settings = MockSettings()
    settings.max_file_size_bytes = 100

    class BigResponse(DummyResponse):
        def __init__(self):
            super().__init__(b"x" * 200)
            self.content_length = 200

    session = DummySession([BigResponse()])
    with pytest.raises(BooksApiError, match="supera el límite"):
        asyncio.run(download_standard_ebooks(session, url, settings))


def test_download_standard_ebooks_client_error():
    url = "https://standardebooks.org/ebooks/book.epub"
    session = DummySession([aiohttp.ClientError("err")])
    with pytest.raises(BooksApiError, match="No se pudo descargar el libro de Standard Ebooks"):
        asyncio.run(download_standard_ebooks(session, url, MockSettings()))
