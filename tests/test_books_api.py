"""API de libros propia (BOOKS_API_*)."""

from __future__ import annotations

import asyncio

import pytest

from bot.services.books_api import (
    BookResult,
    BooksApiError,
    _full_request_url,
    download_book_bytes,
    normalize_book_results,
    search_books,
)
from tests.conftest import PDF, FakeResponse, FakeSession, make_settings

API = make_settings(books_api_base_url="https://api.example", books_api_key="secret")


@pytest.mark.parametrize("key", ["results", "data", "books", "items"])
def test_normalize_accepts_all_list_keys(key):
    payload = {key: [{"id": 1, "title": "A"}, {"book_id": "2", "name": "B"}, {"title": "sin id"}]}
    assert normalize_book_results(payload, max_items=10) == [BookResult("1", "A"), BookResult("2", "B")]


def test_normalize_respects_max_and_bad_payloads():
    assert len(normalize_book_results({"items": [{"id": i} for i in range(9)]}, max_items=3)) == 3
    assert normalize_book_results(["no dict"], max_items=3) == []


def test_full_request_url():
    assert _full_request_url(API, "/search") == "https://api.example/search"
    assert _full_request_url(API, "https://otra/x") == "https://otra/x"


def test_search_sends_key_only_to_the_api():
    session = FakeSession({"api.example": FakeResponse({"results": [{"id": "1", "title": "A"}]})})
    assert asyncio.run(search_books(session, API, "x")) == [BookResult("1", "A")]
    assert session.calls[0]["headers"] == {"Authorization": "Bearer secret"}
    assert session.calls[0]["params"] == [("q", "x")]


def test_download_uses_template_and_fallback_filename():
    session = FakeSession({"api.example/download/42": FakeResponse(body=PDF)})
    data, name = asyncio.run(download_book_bytes(session, API, "42"))
    assert (data, name) == (PDF, "42.pdf")


@pytest.mark.parametrize("call", [
    lambda s, cfg: search_books(s, cfg, "x"),
    lambda s, cfg: download_book_bytes(s, cfg, "1"),
])
def test_requires_base_url(call, settings):
    with pytest.raises(BooksApiError, match="BOOKS_API_BASE_URL"):
        asyncio.run(call(FakeSession(), settings))
