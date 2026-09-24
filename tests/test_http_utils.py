"""Capa HTTP común: reintentos, traducción de errores y descarga con límite."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from bot.services._book_validation import detect_book_type
from bot.services.base import BooksApiError, safe_filename
from bot.services.http_utils import fetch, fetch_book
from tests.conftest import EPUB, PDF, FakeResponse, FakeSession


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ([TimeoutError()] * 3, "tardó demasiado"),
        ([aiohttp.ClientConnectionError()] * 3, "No se pudo contactar"),
        ([FakeResponse(status=503)] * 3, "error HTTP 503"),
        ([FakeResponse(status=404)], "error HTTP 404"),
        ([FakeResponse(ValueError("bad json"))], "datos inválidos"),
    ],
)
def test_fetch_errors_are_user_facing(responses, message):
    with pytest.raises(BooksApiError, match=message):
        asyncio.run(fetch(FakeSession({"x": responses}), "http://x", source="Fuente"))


@pytest.mark.parametrize(
    ("responses", "calls"),
    [
        ([TimeoutError(), FakeResponse({"ok": 1})], 2),
        ([FakeResponse(status=502), FakeResponse(status=500), FakeResponse({"ok": 1})], 3),
    ],
)
def test_fetch_retries_transient_errors(responses, calls):
    session = FakeSession({"x": responses})
    assert asyncio.run(fetch(session, "http://x", source="F")) == {"ok": 1}
    assert len(session.calls) == calls


def test_fetch_does_not_retry_4xx():
    session = FakeSession({"x": FakeResponse(status=404)})
    with pytest.raises(BooksApiError):
        asyncio.run(fetch(session, "http://x", source="F"))
    assert len(session.calls) == 1


def test_fetch_expands_list_params():
    session = FakeSession({"x": FakeResponse({})})
    asyncio.run(fetch(session, "http://x", source="F", params={"fl[]": ["a", "b"], "rows": 3}))
    assert session.calls[0]["params"] == [("fl[]", "a"), ("fl[]", "b"), ("rows", "3")]


@pytest.mark.parametrize(
    ("resp", "limit", "message"),
    [
        (FakeResponse(body=EPUB, content_length=10_000), 100, "supera el límite"),
        (FakeResponse(body=EPUB * 50), 100, "supera el límite"),  # sin Content-Length
        (FakeResponse(body=b"<html>no</html>"), 10_000, "no devolvió un PDF/EPUB"),
        (FakeResponse(status=403), 10_000, "HTTP 403"),
    ],
)
def test_fetch_book_rejects(resp, limit, message):
    with pytest.raises(BooksApiError, match=message):
        asyncio.run(fetch_book(FakeSession({"x": resp}), "http://x", source="F", limit=limit))


def test_fetch_book_detects_type_and_sanitizes_filename():
    resp = FakeResponse(body=PDF, headers={"Content-Disposition": 'attachment; filename=" Mi Libro (2015).PDF"'})
    got = asyncio.run(fetch_book(FakeSession({"x": resp}), "http://x", source="F", limit=10_000))
    assert got.kind == "pdf"
    assert got.filename == "Mi_Libro_2015.pdf"
    assert got.filename_or("otro") == "Mi_Libro_2015.pdf"


@pytest.mark.parametrize(
    ("data", "kind"),
    [(b"%PDF-1", "pdf"), (b"PK\x03\x04", "epub"), (b"BOOKMOBI", "mobi"), (b"<html>", None)],
)
def test_detect_book_type(data, kind):
    assert detect_book_type(data) == kind


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Mi Libro!", "Mi_Libro"), ("   ", "libro"), ("!?*", "libro"), ("a" * 100, "a" * 80)],
)
def test_safe_filename(name, expected):
    assert safe_filename(name) == expected
