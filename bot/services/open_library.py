"""Integración de Open Library para búsqueda de libros."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import aiohttp

from bot.services.books_api import BookResult, BooksApiError

logger = logging.getLogger(__name__)
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"


async def search_open_library(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    params = {"q": query, "limit": max(1, max_results)}
    url = f"{OPEN_LIBRARY_SEARCH_URL}?{urlencode(params)}"
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except asyncio.TimeoutError as e:
        logger.warning("open library timeout: %s", e)
        raise BooksApiError("Open Library tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("open library client error: %s", e)
        raise BooksApiError("No se pudo contactar Open Library.") from e
    except ValueError as e:
        logger.warning("open library invalid json: %s", e)
        raise BooksApiError("Open Library devolvió JSON inválido.") from e

    docs = payload.get("docs") if isinstance(payload, dict) else None
    if not isinstance(docs, list):
        return []

    results: list[BookResult] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        key = str(doc.get("key", "")).strip()
        if not key:
            continue
        title = str(doc.get("title", "")).strip() or "Sin título"
        authors = doc.get("author_name")
        author = ""
        if isinstance(authors, list) and authors:
            author = str(authors[0]).strip()
        label = f"{title} - {author}" if author else title
        results.append(BookResult(id=key, title=label[:500]))
        if len(results) >= max(1, max_results):
            break

    return results
