"""Integración con Internet Archive para búsqueda y descarga de libros.

API pública, sin clave. Documentación:
  https://archive.org/advancedsearch.php  (búsqueda)
  https://archive.org/metadata/{id}       (metadatos + archivos)
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote, urlencode

import aiohttp

from bot.services._book_validation import validate_book_bytes
from bot.services.books_api import BookResult, BooksApiError

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata"
_DOWNLOAD_URL = "https://archive.org/download"

# Orden de preferencia de formatos descargables. IA reporta el formato con
# mayúsculas variables ("EPUB", "Text PDF"...), así que se compara en minúsculas.
_FORMAT_PRIORITY = [
    "epub",
    "application/epub+zip",
    "text pdf",
    "additional text pdf",
    "pdf",
]
_FORMAT_EXT = {
    "epub": ".epub",
    "application/epub+zip": ".epub",
    "text pdf": ".pdf",
    "additional text pdf": ".pdf",
    "pdf": ".pdf",
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
    except TimeoutError as e:
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


def _pick_candidates(files: list, limit: int) -> list[tuple[str, str]]:
    """Devuelve (nombre, extensión) de los archivos descargables, por preferencia.

    Descarta archivos privados (préstamo controlado) y los que según los
    metadatos superan el límite de tamaño.
    """
    by_format: dict[str, list[str]] = {}
    for f in files:
        if not isinstance(f, dict):
            continue
        fmt = str(f.get("format", "")).strip().lower()
        fname = str(f.get("name", "")).strip()
        if fmt not in _FORMAT_EXT or not fname:
            continue
        if str(f.get("private", "")).lower() == "true":
            continue
        try:
            size = int(f.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if size > limit:
            continue
        by_format.setdefault(fmt, []).append(fname)

    candidates: list[tuple[str, str]] = []
    for fmt in _FORMAT_PRIORITY:
        candidates.extend((name, _FORMAT_EXT[fmt]) for name in by_format.get(fmt, []))
    return candidates


async def _fetch_file(
    session: aiohttp.ClientSession,
    url: str,
    limit: int,
) -> bytes:
    timeout_file = aiohttp.ClientTimeout(total=180, connect=10)
    try:
        async with session.get(url, timeout=timeout_file) as resp:
            resp.raise_for_status()
            cl = resp.content_length
            if cl is not None and cl > limit:
                raise BooksApiError(
                    f"El archivo (~{cl // (1024 * 1024)} MB) supera el límite."
                )
            data = await resp.read()
    except TimeoutError as e:
        logger.warning("internet archive download timeout: %s", e)
        raise BooksApiError("Internet Archive tardó demasiado en enviar el archivo.") from e
    except aiohttp.ClientError as e:
        logger.warning("internet archive download client error: %s", e)
        raise BooksApiError("No se pudo descargar el archivo de Internet Archive.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    validate_book_bytes(data)
    return data


async def download_internet_archive(
    session: aiohttp.ClientSession,
    identifier: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga el mejor archivo disponible (epub > pdf) para un identificador."""
    meta_url = f"{_METADATA_URL}/{quote(identifier)}"
    timeout_meta = aiohttp.ClientTimeout(total=20, connect=8)

    try:
        async with session.get(meta_url, timeout=timeout_meta) as resp:
            resp.raise_for_status()
            meta = await resp.json(content_type=None)
    except Exception as e:
        logger.warning("internet archive metadata error: %s", e)
        raise BooksApiError("No se pudieron obtener los metadatos de Internet Archive.") from e

    if not isinstance(meta, dict):
        raise BooksApiError("Internet Archive devolvió datos inválidos.")

    files = meta.get("files")
    if not isinstance(files, list):
        raise BooksApiError("No se encontraron archivos para ese libro en Internet Archive.")

    limit = settings.max_file_size_bytes
    candidates = _pick_candidates(files, limit)
    if not candidates:
        raise BooksApiError("No se encontró un EPUB o PDF descargable en Internet Archive.")

    metadata = meta.get("metadata")
    title = identifier
    if isinstance(metadata, dict) and metadata.get("title"):
        raw_title = metadata["title"]
        title = str(raw_title[0] if isinstance(raw_title, list) else raw_title).strip()

    last_error: BooksApiError | None = None
    for filename_remote, ext in candidates:
        download_url = f"{_DOWNLOAD_URL}/{quote(identifier)}/{quote(filename_remote)}"
        try:
            data = await _fetch_file(session, download_url, limit)
        except BooksApiError as e:
            logger.info("internet archive: %s falló (%s), probando siguiente", filename_remote, e)
            last_error = e
            continue
        return data, f"{_safe_filename(title)}{ext}"

    assert last_error is not None
    raise last_error
