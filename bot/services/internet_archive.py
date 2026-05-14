"""Integración con Internet Archive para búsqueda y descarga de libros.

API pública, sin clave. Documentación:
  https://archive.org/advancedsearch.php  (búsqueda)
  https://archive.org/metadata/{id}       (metadatos + archivos)
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlencode

import aiohttp

from bot.services.books_api import BookResult, BooksApiError
from bot.services._book_validation import validate_book_bytes

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata"
_DOWNLOAD_URL = "https://archive.org/download"

# Preference order for downloadable formats
_FORMAT_PRIORITY = [
    "epub",
    "application/epub+zip",
    "Text PDF",
    "Additional Text PDF",
    "PDF",
]
_FORMAT_EXT = {
    "epub": ".epub",
    "application/epub+zip": ".epub",
    "Text PDF": ".pdf",
    "Additional Text PDF": ".pdf",
    "PDF": ".pdf",
}


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip())[:80]
    return base or "libro"


async def search_internet_archive(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    params = {
        "q": f"{query} AND mediatype:texts AND NOT access-restricted-item:true",
        "fl[]": ["identifier", "title", "creator"],
        "output": "json",
        "rows": max(1, max_results),
        "page": 1,
        "sort[]": "downloads desc",
    }
    url = f"{_SEARCH_URL}?{urlencode(params, doseq=True)}"
    timeout = aiohttp.ClientTimeout(total=25, connect=8)

    try:
        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
    except asyncio.TimeoutError as e:
        logger.warning("internet archive search timeout: %s", e)
        raise BooksApiError("Internet Archive tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("internet archive search client error: %s", e)
        raise BooksApiError("No se pudo contactar Internet Archive.") from e
    except ValueError as e:
        logger.warning("internet archive search invalid json: %s", e)
        raise BooksApiError("Internet Archive devolvió datos inválidos.") from e

    try:
        docs = payload["response"]["docs"]
    except (KeyError, TypeError):
        return []

    results: list[BookResult] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        identifier = str(doc.get("identifier", "")).strip()
        if not identifier:
            continue
        title = str(doc.get("title", "")).strip() or "Sin título"
        creator = doc.get("creator")
        if isinstance(creator, list):
            creator = creator[0] if creator else ""
        creator = str(creator or "").strip()
        label = f"{title} - {creator}" if creator else title
        results.append(BookResult(id=identifier, title=label[:500]))
        if len(results) >= max(1, max_results):
            break

    return results


async def download_internet_archive(
    session: aiohttp.ClientSession,
    identifier: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga el mejor archivo disponible (epub > pdf) para un identificador."""
    meta_url = f"{_METADATA_URL}/{identifier}"
    timeout_meta = aiohttp.ClientTimeout(total=20, connect=8)

    try:
        async with session.get(meta_url, timeout=timeout_meta) as resp:
            resp.raise_for_status()
            meta = await resp.json(content_type=None)
    except Exception as e:
        logger.warning("internet archive metadata error: %s", e)
        raise BooksApiError("No se pudieron obtener los metadatos de Internet Archive.") from e

    files = meta.get("files")
    if not isinstance(files, list):
        raise BooksApiError("No se encontraron archivos para ese libro en Internet Archive.")

    # Build candidate map: format -> filename
    candidates: dict[str, str] = {}
    for f in files:
        if not isinstance(f, dict):
            continue
        fmt = f.get("format", "")
        fname = f.get("name", "")
        if fmt in _FORMAT_EXT and fname and fmt not in candidates:
            candidates[fmt] = fname

    chosen_fmt = next((f for f in _FORMAT_PRIORITY if f in candidates), None)
    if not chosen_fmt:
        raise BooksApiError("No se encontró un EPUB o PDF descargable en Internet Archive.")

    filename_remote = candidates[chosen_fmt]
    ext = _FORMAT_EXT[chosen_fmt]
    download_url = f"{_DOWNLOAD_URL}/{identifier}/{filename_remote}"
    limit = settings.max_file_size_bytes
    timeout_file = aiohttp.ClientTimeout(total=120, connect=10)

    try:
        async with session.get(download_url, timeout=timeout_file) as resp:
            resp.raise_for_status()
            cl = resp.content_length
            if cl is not None and cl > limit:
                raise BooksApiError(
                    f"El archivo (~{cl // (1024 * 1024)} MB) supera el límite."
                )
            data = await resp.read()
    except aiohttp.ClientError as e:
        logger.warning("internet archive download client error: %s", e)
        raise BooksApiError("No se pudo descargar el archivo de Internet Archive.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    validate_book_bytes(data)

    title = str(meta.get("metadata", {}).get("title", identifier)).strip()
    out_filename = f"{_safe_filename(title)}{ext}"
    return data, out_filename
