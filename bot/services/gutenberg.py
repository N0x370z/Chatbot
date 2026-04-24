"""Integración con el catálogo de Project Gutenberg vía Gutendex."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlencode

import aiohttp

from bot.services.books_api import BookResult, BooksApiError

logger = logging.getLogger(__name__)
GUTENDEX_SEARCH_URL = "https://gutendex.com/books"
GUTENDEX_BOOK_URL = "https://gutendex.com/books"


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip())[:80]
    return base or "libro"


async def search_gutenberg(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    params = {"search": query}
    url = f"{GUTENDEX_SEARCH_URL}?{urlencode(params)}"
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except asyncio.TimeoutError as e:
        logger.warning("gutenberg timeout: %s", e)
        raise BooksApiError("Gutenberg tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("gutenberg client error: %s", e)
        raise BooksApiError("No se pudo contactar Gutenberg.") from e
    except ValueError as e:
        logger.warning("gutenberg invalid json: %s", e)
        raise BooksApiError("Gutenberg devolvió JSON inválido.") from e

    results_raw = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results_raw, list):
        return []

    results: list[BookResult] = []
    for item in results_raw:
        if not isinstance(item, dict):
            continue
        book_id = item.get("id")
        if book_id is None:
            continue
        title = str(item.get("title", "")).strip() or "Sin título"
        authors = item.get("authors")
        author = ""
        if isinstance(authors, list) and authors:
            first_author = authors[0]
            if isinstance(first_author, dict):
                author = str(first_author.get("name", "")).strip()
            else:
                author = str(first_author).strip()
        label = f"{title} - {author}" if author else title
        results.append(BookResult(id=str(book_id), title=label[:500]))
        if len(results) >= max(1, max_results):
            break

    return results


async def download_gutenberg(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    url = f"{GUTENDEX_BOOK_URL}/{book_id}"
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except asyncio.TimeoutError as e:
        logger.warning("gutenberg metadata timeout: %s", e)
        raise BooksApiError("Gutenberg tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("gutenberg metadata client error: %s", e)
        raise BooksApiError("No se pudo contactar Gutenberg.") from e
    except ValueError as e:
        logger.warning("gutenberg metadata invalid json: %s", e)
        raise BooksApiError("Gutenberg devolvió JSON inválido.") from e

    formats = payload.get("formats")
    if not isinstance(formats, dict):
        raise BooksApiError("Gutenberg no encontró el archivo EPUB para ese libro.")

    epub_url = formats.get("application/epub+zip")
    if not epub_url:
        epub_url = formats.get("application/x-epub+zip")
    if not epub_url:
        raise BooksApiError("No se encontró un EPUB descargable en Gutenberg.")

    limit = settings.max_file_size_bytes
    try:
        async with session.get(epub_url) as resp:
            resp.raise_for_status()
            content_length = resp.content_length
            if content_length is not None and content_length > limit:
                raise BooksApiError(
                    f"El archivo remoto (~{content_length // (1024 * 1024)} MB) supera el límite."
                )
            data = await resp.read()
    except aiohttp.ClientError as e:
        logger.warning("gutenberg download client error: %s", e)
        raise BooksApiError("No se pudo descargar el EPUB de Gutenberg.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    title = str(payload.get("title", "libro")).strip()
    filename = f"{_safe_filename(title)}.epub"
    return data, filename
