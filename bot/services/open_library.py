"""Open Library: búsqueda en el catálogo y descarga vía Internet Archive.

Open Library es un catálogo: no aloja archivos. Los libros de dominio público
que muestra están digitalizados en Internet Archive, así que la búsqueda se
limita a obras con ``ebook_access:public`` y la descarga localiza sus copias
públicas en Internet Archive.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label
from bot.services.http_utils import fetch
from bot.services.internet_archive import download_internet_archive, public_identifiers

logger = logging.getLogger(__name__)

SOURCE = "Open Library"
SEARCH_URL = "https://openlibrary.org/search.json"
_WORK_ID_RE = re.compile(r"OL\d+W")
# Copias de IA que se consultan y que se prueban por obra antes de rendirse.
_MAX_IA_LOOKUP = 40
_MAX_IA_CANDIDATES = 3


def parse_search(payload: Any, max_results: int) -> list[BookResult]:
    docs = payload.get("docs") if isinstance(payload, dict) else None
    results: list[BookResult] = []
    for doc in docs if isinstance(docs, list) else []:
        if not isinstance(doc, dict) or not str(doc.get("key", "")).strip():
            continue
        authors = doc.get("author_name")
        author = str(authors[0]) if isinstance(authors, list) and authors else ""
        results.append(BookResult(id=str(doc["key"]).strip(), title=book_label(str(doc.get("title", "")), author)))
        if len(results) >= max(1, max_results):
            break
    return results


async def search_open_library(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    payload = await fetch(
        session,
        SEARCH_URL,
        source=SOURCE,
        params={
            "q": f"{query} ebook_access:public",
            "fields": "key,title,author_name",
            "limit": max(1, max_results),
        },
    )
    return parse_search(payload, max_results)


async def download_open_library(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga una obra probando sus copias públicas en IA (más descargadas primero)."""
    match = _WORK_ID_RE.search(book_id)
    if not match:
        raise BooksApiError("ID de Open Library inválido.")
    work_id = match.group(0)

    # Open Library lista todas las copias de la obra en IA (libres y de
    # préstamo); IA filtra las de acceso libre.
    payload = await fetch(
        session, SEARCH_URL, source=SOURCE, params={"q": f"key:/works/{work_id}", "fields": "ia"}
    )
    docs = payload.get("docs") if isinstance(payload, dict) else None
    ia_ids = docs[0].get("ia") if isinstance(docs, list) and docs and isinstance(docs[0], dict) else None
    ia_ids = [str(i) for i in ia_ids[:_MAX_IA_LOOKUP]] if isinstance(ia_ids, list) else []
    identifiers = await public_identifiers(session, ia_ids, _MAX_IA_CANDIDATES)
    if not identifiers:
        raise BooksApiError(
            "Esta obra no tiene una copia de descarga libre. "
            f"Referencia: https://openlibrary.org/works/{work_id}"
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
