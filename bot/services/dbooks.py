"""Integración de DBooks API para descarga de libros IT y Open Source."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import aiohttp

from bot.services.books_api import BookResult, BooksApiError
from bot.services.libgen import _safe_filename

logger = logging.getLogger(__name__)

DBOOKS_SEARCH_URL = "https://www.dbooks.org/api/search/"
DBOOKS_BOOK_URL = "https://www.dbooks.org/api/book/"


async def search_dbooks(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    # La búsqueda de dbooks usa la ruta directamente: /api/search/<query>
    safe_query = query.strip().replace(" ", "+")
    url = f"{DBOOKS_SEARCH_URL}{safe_query}"
    timeout = aiohttp.ClientTimeout(total=20, connect=8)

    try:
        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except asyncio.TimeoutError as e:
        logger.warning("dbooks search timeout: %s", e)
        raise BooksApiError("dBooks tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("dbooks search client error: %s", e)
        raise BooksApiError("No se pudo contactar con dBooks.") from e
    except ValueError as e:
        logger.warning("dbooks search invalid json: %s", e)
        raise BooksApiError("dBooks devolvió datos inválidos.") from e

    if payload.get("status") != "ok":
        return []

    books = payload.get("books")
    if not isinstance(books, list):
        return []

    results: list[BookResult] = []
    for book in books:
        book_id = str(book.get("id", "")).strip()
        if not book_id:
            continue
        title = str(book.get("title", "")).strip() or "Sin título"
        authors = str(book.get("authors", "")).strip()
        label = f"{title} - {authors}" if authors else title
        results.append(BookResult(id=book_id, title=label[:500]))
        if len(results) >= max(1, max_results):
            break

    return results


async def download_dbooks(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    url = f"{DBOOKS_BOOK_URL}{book_id}"
    timeout_page = aiohttp.ClientTimeout(total=20, connect=8)
    
    try:
        async with session.get(url, timeout=timeout_page) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except Exception as e:
        logger.warning("dbooks get metadata error: %s", e)
        raise BooksApiError("No se pudo obtener información del libro en dBooks.") from e

    if payload.get("status") != "ok":
        raise BooksApiError("El libro no está disponible en dBooks.")

    download_url = payload.get("download")
    if not download_url:
        raise BooksApiError("No se encontró un link de descarga directo en dBooks.")

    limit = settings.max_file_size_bytes
    timeout_file = aiohttp.ClientTimeout(total=120, connect=10)

    try:
        async with session.get(download_url, timeout=timeout_file) as resp:
            resp.raise_for_status()
            content_length = resp.content_length
            if content_length is not None and content_length > limit:
                raise BooksApiError(
                    f"El archivo (~{content_length // (1024*1024)} MB) supera el límite."
                )
            data = await resp.read()
    except aiohttp.ClientError as e:
        logger.error("dbooks download client error: %s", e)
        raise BooksApiError("No se pudo descargar el archivo desde dBooks.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    title = str(payload.get("title", "libro")).strip()
    filename = f"{_safe_filename(title)}.pdf"

    return data, filename
