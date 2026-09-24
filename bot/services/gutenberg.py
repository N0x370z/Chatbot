"""Project Gutenberg vía Gutendex (https://gutendex.com)."""

from __future__ import annotations

from typing import Any

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label, safe_filename
from bot.services.http_utils import fetch, fetch_book

SOURCE = "Gutenberg"
GUTENDEX_URL = "https://gutendex.com/books"
# Gutendex cae con frecuencia; un timeout corto evita bloquear el respaldo.
_TIMEOUT = aiohttp.ClientTimeout(total=12, connect=6)
_EPUB_TYPES = ("application/epub+zip", "application/x-epub+zip")


def parse_search(payload: Any, max_results: int) -> list[BookResult]:
    items = payload.get("results") if isinstance(payload, dict) else None
    results: list[BookResult] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        authors = item.get("authors")
        author = ""
        if isinstance(authors, list) and authors:
            first = authors[0]
            author = str(first.get("name", "")) if isinstance(first, dict) else str(first)
        results.append(BookResult(id=str(item["id"]), title=book_label(str(item.get("title", "")), author)))
        if len(results) >= max(1, max_results):
            break
    return results


async def search_gutenberg(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    payload = await fetch(session, GUTENDEX_URL, source=SOURCE, params={"search": query}, timeout=_TIMEOUT)
    return parse_search(payload, max_results)


async def download_gutenberg(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    payload = await fetch(session, f"{GUTENDEX_URL}/{book_id}", source=SOURCE, timeout=_TIMEOUT)
    formats = payload.get("formats") if isinstance(payload, dict) else None
    epub_url = next((formats[t] for t in _EPUB_TYPES if formats.get(t)), None) if isinstance(formats, dict) else None
    if not epub_url:
        raise BooksApiError("No se encontró un EPUB descargable en Gutenberg.")

    got = await fetch_book(session, epub_url, source=SOURCE, limit=settings.max_file_size_bytes)
    return got.data, f"{safe_filename(str(payload.get('title', 'libro')))}.epub"
