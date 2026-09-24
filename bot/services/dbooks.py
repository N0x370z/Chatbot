"""dBooks (https://www.dbooks.org): libros técnicos y open source gratuitos."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, quote_plus

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label, safe_filename
from bot.services.http_utils import fetch, fetch_book

SOURCE = "dBooks"
DBOOKS_SEARCH_URL = "https://www.dbooks.org/api/search/"
DBOOKS_BOOK_URL = "https://www.dbooks.org/api/book/"


def parse_search(payload: Any, max_results: int) -> list[BookResult]:
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return []
    books = payload.get("books")
    results: list[BookResult] = []
    for book in books if isinstance(books, list) else []:
        if not isinstance(book, dict) or not str(book.get("id", "")).strip():
            continue
        results.append(
            BookResult(
                id=str(book["id"]).strip(),
                title=book_label(str(book.get("title", "")), str(book.get("authors", ""))),
            )
        )
        if len(results) >= max(1, max_results):
            break
    return results


async def search_dbooks(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    # dBooks recibe la búsqueda en la ruta: /api/search/<query>, con los
    # espacios como "+" (con "%20" responde 403).
    payload = await fetch(session, f"{DBOOKS_SEARCH_URL}{quote_plus(query.strip())}", source=SOURCE)
    return parse_search(payload, max_results)


async def download_dbooks(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    payload = await fetch(session, f"{DBOOKS_BOOK_URL}{quote(book_id)}", source=SOURCE)
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise BooksApiError("El libro no está disponible en dBooks.")
    download_url = payload.get("download")
    if not download_url:
        raise BooksApiError("No se encontró un link de descarga directo en dBooks.")

    got = await fetch_book(session, download_url, source=SOURCE, limit=settings.max_file_size_bytes)
    return got.data, f"{safe_filename(str(payload.get('title', 'libro')))}.{got.kind}"
