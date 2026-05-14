"""Tests de parser de Libgen."""

from __future__ import annotations

from bot.services.libgen import _parse_libgen_search_html, _safe_filename

def test_safe_filename() -> None:
    # spaces converted to underscores and special chars stripped
    assert _safe_filename("Hola Mundo!?*") == "Hola_Mundo"
    # empty string -> "libro"
    assert _safe_filename("   ") == "libro"
    assert _safe_filename("!?*") == "libro"
    # longer than 80 chars truncated
    long_name = "a" * 100
    assert _safe_filename(long_name) == "a" * 80



def test_parse_libgen_search_html_extracts_download_urls() -> None:
    html = (
        '<table>'
        '<tr><th>ID</th><th>Author</th><th>Title</th><th>Links</th></tr>'
        '<tr>'
        '<td>1</td>'
        '<td>Juan Pérez</td>'
        '<td><a href="/book/index.php?md5=abc123">Libro de prueba</a></td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td><a href="/get.php?md5=abc123">GET</a></td>'
        '</tr>'
        '</table>'
    )

    results = _parse_libgen_search_html(html, "https://libgen.is", max_results=5)

    assert len(results) == 1
    assert results[0].id == "https://libgen.is/get.php?md5=abc123"
    assert results[0].title == "Libro de prueba - Juan Pérez"


import asyncio
from bot.services.libgen import search_libgen

class DummyResponse:
    def __init__(self, text_data, status=200):
        self._text_data = text_data
        self.status = status
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    def raise_for_status(self): pass
    async def text(self): return self._text_data

class DummySession:
    def __init__(self, responses):
        self.responses = responses
    def get(self, url, **kwargs):
        return self.responses[0]

class MockSettings:
    ssl_verify = True

def test_search_libgen_success() -> None:
    html = (
        '<table>'
        '<tr><th>ID</th><th>Author</th><th>Title</th><th>Links</th></tr>'
        '<tr>'
        '<td><a href="/book/index.php?md5=abc123">Libro de prueba</a></td>'
        '<td>Juan Pérez</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td>Fake</td>'
        '<td><a href="/get.php?md5=abc123">GET</a></td>'
        '<td>Fake</td>'
        '</tr>'
        '</table>'
    )
    session = DummySession([DummyResponse(html)])
    results = asyncio.run(search_libgen(session, "query", 5, MockSettings()))
    assert len(results) == 1
    assert results[0].title == "Libro de prueba - Juan Pérez"
