"""Integración de Open Library para búsqueda y descarga de libros.

Open Library es un catálogo: no aloja archivos. Los libros de dominio público
que muestra están digitalizados en Internet Archive, así que la búsqueda se
limita a obras con ``ebook_access:public`` y la descarga localiza sus copias
públicas en Internet Archive.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

import aiohttp

from bot.services.books_api import BookResult, BooksApiError
from bot.services.http_utils import _retry_get
from bot.services.internet_archive import download_internet_archive

logger = logging.getLogger(__name__)
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
IA_SEARCH_URL = "https://archive.org/advancedsearch.php"
_SEARCH_FIELDS = "key,title,author_name"
_WORK_ID_RE = re.compile(r"OL\d+W")
# Copias de IA que se prueban por obra antes de rendirse.
_MAX_IA_CANDIDATES = 4


async def search_open_library(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    params = {
        "q": f"{query} ebook_access:public",
        "fields": _SEARCH_FIELDS,
        "limit": max(1, max_results),
    }
    url = f"{OPEN_LIBRARY_SEARCH_URL}?{urlencode(params)}"

    # Timeout propio más generoso que el global
    timeout = aiohttp.ClientTimeout(total=30, connect=10)

    try:
        resp = await _retry_get(session, url, timeout=timeout)
        resp.raise_for_status()
        payload = await resp.json(content_type=None)
    except TimeoutError as e:
        logger.warning("open library timeout: %s", e)
        raise BooksApiError(
            "Open Library tardó demasiado. Prueba con /fuente internet_archive"
        ) from e
    except aiohttp.ClientError as e:
        logger.warning("open library client error: %s", e)
        raise BooksApiError(
            "No se pudo contactar Open Library. Prueba con /fuente internet_archive"
        ) from e
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


async def _public_ia_identifiers(
    session: aiohttp.ClientSession,
    work_id: str,
) -> list[str]:
    """Identificadores de IA de acceso libre para una obra, más descargados primero."""
    params = {
        "q": f"openlibrary_work:{work_id} AND mediatype:texts AND NOT access-restricted-item:true",
        "fl[]": "identifier",
        "rows": _MAX_IA_CANDIDATES,
        "sort[]": "downloads desc",
        "output": "json",
    }
    url = f"{IA_SEARCH_URL}?{urlencode(params)}"
    timeout = aiohttp.ClientTimeout(total=20, connect=8)
    try:
        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as e:
        logger.warning("open library → IA lookup error: %s", e)
        raise BooksApiError("No se pudo localizar el archivo en Internet Archive.") from e

    try:
        docs = payload["response"]["docs"]
    except (KeyError, TypeError):
        return []
    return [
        str(d["identifier"]).strip()
        for d in docs
        if isinstance(d, dict) and str(d.get("identifier", "")).strip()
    ]


async def download_open_library(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga una obra de Open Library a través de su copia pública en IA."""
    match = _WORK_ID_RE.search(book_id)
    if not match:
        raise BooksApiError("ID de Open Library inválido.")

    identifiers = await _public_ia_identifiers(session, match.group(0))
    if not identifiers:
        raise BooksApiError(
            "Esta obra no tiene una copia de descarga libre. "
            f"Referencia: https://openlibrary.org/works/{match.group(0)}"
        )

    last_error: BooksApiError | None = None
    for identifier in identifiers:
        try:
            return await download_internet_archive(session, identifier, settings)
        except BooksApiError as e:
            logger.info("open library: copia IA %s no sirvió (%s)", identifier, e)
            last_error = e

    assert last_error is not None
    raise last_error
