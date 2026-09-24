"""Fuentes de libros: interpretación de respuestas y flujo de descarga.

Los errores de red/HTTP se prueban una sola vez en test_http_utils.py; aquí
solo lo específico de cada fuente.
"""

from __future__ import annotations

import asyncio

import pytest

from bot.services import dbooks, gutenberg, internet_archive, libgen, open_library, standard_ebooks
from bot.services.base import BookResult, BooksApiError
from bot.services.sources import DEFAULT_SOURCE, SOURCES
from tests.conftest import EPUB, PDF, FakeResponse, FakeSession


def run(coro):
    return asyncio.run(coro)


# ── Registro ─────────────────────────────────────────────────────────────────

def test_registry_default_and_order():
    assert DEFAULT_SOURCE in SOURCES
    assert list(SOURCES)[0] == DEFAULT_SOURCE
    # Las fuentes que suelen fallar van al final de la cadena de respaldo.
    assert list(SOURCES)[-2:] == ["gutenberg", "standard_ebooks"]


# ── Parsers (sin red) ────────────────────────────────────────────────────────

OPDS = b"""<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Pride and Prejudice</title><author><name>Jane Austen</name></author>
    <link type="application/epub+zip" href="https://se.org/pp.epub"/></entry>
  <entry><title>Emma</title><author><name>Jane Austen</name></author></entry>
  <entry><title>Dracula</title><author><name>Bram Stoker</name></author>
    <link type="application/epub+zip" href="https://se.org/d.epub"/></entry>
</feed>"""

LIBGEN_ROW = (
    "<tr><td><a title=\"Add: 2019<br>ID: 1\" href=\"edition.php?id=1\">Python Crash Course</a></td>"
    "<td>Eric Matthes</td><td>No Starch</td><td>2019</td><td>English</td><td>544</td>"
    "<td><a href=\"/file.php?id=1\">5 MB</a></td><td>{ext}</td>"
    "<td><a href=\"/ads.php?md5=abc\">1</a><a href=\"https://mirror.example/x\">2</a></td></tr>"
)


@pytest.mark.parametrize(
    ("parse", "payload", "expected"),
    [
        (
            open_library.parse_search,
            {"docs": [{"key": "/works/OL1W", "title": "Don Quijote", "author_name": ["Cervantes"]}, {"title": "sin key"}]},
            [BookResult("/works/OL1W", "Don Quijote - Cervantes")],
        ),
        (
            internet_archive.parse_ia_search,
            {"response": {"docs": [{"identifier": "id1", "title": "Linux", "creator": ["Ana", "Bo"]}, {"identifier": "id2"}]}},
            [BookResult("id1", "Linux - Ana"), BookResult("id2", "Sin título")],
        ),
        (
            gutenberg.parse_search,
            {"results": [{"id": 84, "title": "Frankenstein", "authors": [{"name": "Shelley, Mary"}]}]},
            [BookResult("84", "Frankenstein - Shelley, Mary")],
        ),
        (
            dbooks.parse_search,
            {"status": "ok", "books": [{"id": "123", "title": "Think Python", "authors": "Downey"}]},
            [BookResult("123", "Think Python - Downey")],
        ),
        (dbooks.parse_search, {"status": "not found"}, []),
        (open_library.parse_search, "no es json", []),
    ],
)
def test_parse_search(parse, payload, expected):
    assert parse(payload, 10) == expected


def test_parsers_respect_max_results():
    docs = {"response": {"docs": [{"identifier": f"id{i}"} for i in range(10)]}}
    assert len(internet_archive.parse_ia_search(docs, 3)) == 3


def test_parse_opds_filters_locally_and_skips_entries_without_epub():
    results = standard_ebooks._parse_opds(OPDS, "austen", 10)
    assert results == [BookResult("https://se.org/pp.epub", "Pride and Prejudice - Jane Austen")]
    with pytest.raises(BooksApiError, match="XML inválido"):
        standard_ebooks._parse_opds(b"<roto", "x", 10)


def test_parse_libgen_uses_edition_title_and_filters_formats():
    html = "<table><tr><th>h</th></tr>" + LIBGEN_ROW.format(ext="epub") + LIBGEN_ROW.format(ext="djvu") + "</table>"
    results = libgen._parse_libgen_search_html(html, "https://libgen.li", 10)
    assert results == [
        BookResult("https://libgen.li/ads.php?md5=abc", "Python Crash Course - Eric Matthes (epub · 5 MB)")
    ]


def test_ia_pick_files_prefers_small_epub_and_skips_private_or_huge():
    files = [
        {"name": "big.pdf", "format": "Text PDF", "size": "900"},
        {"name": "b.epub", "format": "EPUB", "size": "300"},
        {"name": "a.epub", "format": "EPUB", "size": "200"},
        {"name": "lent.epub", "format": "EPUB", "private": "true"},
        {"name": "huge.pdf", "format": "PDF", "size": "99999"},
        {"name": "x.djvu", "format": "DjVu"},
    ]
    assert internet_archive.pick_files(files, limit=1000) == [
        ("a.epub", ".epub"), ("b.epub", ".epub"), ("big.pdf", ".pdf"),
    ]


# ── Flujos de descarga ───────────────────────────────────────────────────────

IA_META = {
    "metadata": {"title": "Don Quijote"},
    "files": [{"name": "q.epub", "format": "EPUB"}, {"name": "q.pdf", "format": "Text PDF"}],
}


def test_ia_download_falls_back_to_next_file(settings):
    session = FakeSession({
        "/metadata/": FakeResponse(IA_META),
        "q.epub": FakeResponse(status=500),
        "q.pdf": FakeResponse(body=PDF),
    })
    data, name = run(internet_archive.download_internet_archive(session, "quijote", settings))
    assert (data, name) == (PDF, "Don_Quijote.pdf")


def test_ia_download_without_downloadable_files(settings):
    session = FakeSession({"/metadata/": FakeResponse({"files": [{"name": "x.djvu", "format": "DjVu"}]})})
    with pytest.raises(BooksApiError, match="No se encontró un EPUB o PDF"):
        run(internet_archive.download_internet_archive(session, "x", settings))


def test_open_library_download_uses_public_ia_copy(settings):
    session = FakeSession({
        "openlibrary.org/search.json": FakeResponse({"docs": [{"ia": ["prestado", "libre"]}]}),
        "advancedsearch": FakeResponse({"response": {"docs": [{"identifier": "libre"}]}}),
        "/metadata/libre": FakeResponse(IA_META),
        "/download/libre/q.epub": FakeResponse(body=EPUB),
    })
    data, name = run(open_library.download_open_library(session, "/works/OL503580W", settings))
    assert (data, name) == (EPUB, "Don_Quijote.epub")
    ia_query = dict(session.calls[1]["params"])["q"]
    assert "identifier:(prestado OR libre)" in ia_query
    assert "NOT access-restricted-item:true" in ia_query


def test_open_library_download_without_public_copy(settings):
    session = FakeSession({
        "openlibrary.org": FakeResponse({"docs": [{"ia": ["prestado"]}]}),
        "advancedsearch": FakeResponse({"response": {"docs": []}}),
    })
    with pytest.raises(BooksApiError, match="no tiene una copia de descarga libre"):
        run(open_library.download_open_library(session, "/works/OL1W", settings))


def test_open_library_search_only_public_ebooks():
    session = FakeSession({"openlibrary.org": FakeResponse({"docs": []})})
    run(open_library.search_open_library(session, "quijote", 5))
    assert dict(session.calls[0]["params"])["q"] == "quijote ebook_access:public"


@pytest.mark.parametrize(
    ("download", "book_id", "routes", "expected_name"),
    [
        (
            gutenberg.download_gutenberg, "84",
            {"gutendex.com/books/84": FakeResponse({"title": "Frankenstein", "formats": {"application/epub+zip": "https://gutenberg.org/84.epub"}}),
             "84.epub": FakeResponse(body=EPUB)},
            "Frankenstein.epub",
        ),
        (
            dbooks.download_dbooks, "123",
            {"api/book/123": FakeResponse({"status": "ok", "title": "Think Python", "download": "https://dbooks.org/d/123"}),
             "dbooks.org/d/123": FakeResponse(body=PDF)},
            "Think_Python.pdf",
        ),
        (
            standard_ebooks.download_standard_ebooks, "https://se.org/pp.epub",
            {"pp.epub": FakeResponse(body=EPUB)},
            "pp.epub",
        ),
        (
            libgen.download_libgen, "https://libgen.li/ads.php?md5=abc",
            {"ads.php": FakeResponse(text='<a href="get.php?md5=abc&key=K">GET</a>'),
             "get.php": FakeResponse(body=EPUB, headers={"Content-Disposition": 'attachment; filename="Python.epub"'})},
            "Python.epub",
        ),
    ],
)
def test_source_download_happy_path(settings, download, book_id, routes, expected_name):
    data, name = run(download(FakeSession(routes), book_id, settings))
    assert data in (EPUB, PDF)
    assert name == expected_name


@pytest.mark.parametrize(
    ("book_id", "message"),
    [
        ("https://libgen.li.attacker.com/get.php?md5=abc", "no está permitido"),
        ("https://evil.com/ads.php?md5=abc", "intermediario no permitido"),
        ("not-a-url", "ID de Libgen inválido"),
    ],
)
def test_libgen_rejects_untrusted_domains(settings, book_id, message):
    with pytest.raises(BooksApiError, match=message):
        run(libgen.download_libgen(FakeSession(), book_id, settings))


def test_libgen_rejects_intermediate_link_to_other_domain(settings):
    session = FakeSession({"ads.php": FakeResponse(text='<a href="https://evil.com/get.php?x">GET</a>')})
    with pytest.raises(BooksApiError, match="no está permitido"):
        run(libgen.download_libgen(session, "https://libgen.li/ads.php?md5=abc", settings))


def test_dbooks_search_encodes_spaces_as_plus():
    session = FakeSession({"dbooks.org": FakeResponse({"status": "ok", "books": []})})
    run(dbooks.search_dbooks(session, "python crash", 5))
    assert session.calls[0]["url"].endswith("/api/search/python+crash")


def test_libgen_sends_browser_user_agent():
    session = FakeSession({"libgen.li": FakeResponse(text="<table></table>")})
    run(libgen.search_libgen(session, "python", 5))
    assert "Mozilla" in session.calls[0]["headers"]["User-Agent"]
