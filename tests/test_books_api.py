"""Tests del parser de resultados de la API de libros."""

from __future__ import annotations

from bot.services.books_api import BookResult, normalize_book_results


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
