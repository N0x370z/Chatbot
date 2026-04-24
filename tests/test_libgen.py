"""Tests de parser de Libgen."""

from __future__ import annotations

from bot.services.libgen import _parse_libgen_search_html


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
