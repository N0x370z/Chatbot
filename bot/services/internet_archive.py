"""Internet Archive: búsqueda y descarga de libros de acceso libre.

API pública, sin clave:
  https://archive.org/advancedsearch.php  (búsqueda)
  https://archive.org/metadata/{id}       (metadatos + archivos)
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label, safe_filename
from bot.services.http_utils import fetch, fetch_book

logger = logging.getLogger(__name__)

SOURCE = "Internet Archive"
SEARCH_URL = "https://archive.org/advancedsearch.php"
_METADATA_URL = "https://archive.org/metadata"
_DOWNLOAD_URL = "https://archive.org/download"

# Formatos por preferencia. IA los reporta con mayúsculas variables
# ("EPUB", "Text PDF"...), así que se comparan en minúsculas.
_FORMAT_EXT = {
    "epub": ".epub",
    "application/epub+zip": ".epub",
    "text pdf": ".pdf",
    "additional text pdf": ".pdf",
    "pdf": ".pdf",
}
_FORMAT_PRIORITY = list(_FORMAT_EXT)
# Filtro de búsqueda: solo ítems que tengan algún formato descargable.
_FORMAT_QUERY = 'format:(EPUB OR "Text PDF" OR PDF)'
# Archivos que se prueban por ítem. Las colecciones pueden tener cientos de
# EPUB y los servidores de IA son lentos: probar todos puede tardar minutos.
MAX_FILE_ATTEMPTS = 3


def _first(value: Any) -> str:
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def parse_ia_search(payload: Any, max_results: int) -> list[BookResult]:
    try:
        docs = payload["response"]["docs"]
    except (KeyError, TypeError):
        return []
    results: list[BookResult] = []
    for doc in docs if isinstance(docs, list) else []:
        if not isinstance(doc, dict) or not _first(doc.get("identifier")):
            continue
        results.append(
            BookResult(
                id=_first(doc["identifier"]),
                title=book_label(_first(doc.get("title")), _first(doc.get("creator"))),
            )
        )
        if len(results) >= max(1, max_results):
            break
    return results


def pick_files(files: Any, limit: int) -> list[tuple[str, str]]:
    """(nombre, extensión) de los archivos descargables, por preferencia.

    Descarta archivos privados (préstamo controlado) y los que según los
    metadatos superan el límite de tamaño. Dentro de cada formato, el más
    pequeño primero: suele ser el mismo libro y llega antes.
    """
    by_format: dict[str, list[tuple[int, str]]] = {}
    for f in files if isinstance(files, list) else []:
        if not isinstance(f, dict):
            continue
        fmt = str(f.get("format", "")).strip().lower()
        name = str(f.get("name", "")).strip()
        if fmt not in _FORMAT_EXT or not name or str(f.get("private", "")).lower() == "true":
            continue
        try:
            size = int(f.get("size", 0))
        except (TypeError, ValueError):
            size = 0
        if size > limit:
            continue
        by_format.setdefault(fmt, []).append((size, name))
    return [
        (name, _FORMAT_EXT[fmt])
        for fmt in _FORMAT_PRIORITY
        for _, name in sorted(by_format.get(fmt, []))
    ]


async def search_internet_archive(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    payload = await fetch(
        session,
        SEARCH_URL,
        source=SOURCE,
        params={
            "q": f"({query}) AND mediatype:texts AND NOT access-restricted-item:true AND {_FORMAT_QUERY}",
            "fl[]": ["identifier", "title", "creator"],
            "rows": max(1, max_results),
            "sort[]": "downloads desc",
            "output": "json",
        },
    )
    return parse_ia_search(payload, max_results)


async def public_identifiers(
    session: aiohttp.ClientSession,
    identifiers: list[str],
    max_results: int,
) -> list[str]:
    """Filtra ``identifiers`` a los de acceso libre con EPUB/PDF, más descargados primero."""
    ids = [i for i in identifiers if i.replace("_", "").replace("-", "").replace(".", "").isalnum()]
    if not ids:
        return []
    payload = await fetch(
        session,
        SEARCH_URL,
        source=SOURCE,
        params={
            "q": f"identifier:({' OR '.join(ids)}) AND NOT access-restricted-item:true AND {_FORMAT_QUERY}",
            "fl[]": "identifier",
            "rows": max(1, max_results),
            "sort[]": "downloads desc",
            "output": "json",
        },
    )
    return [r.id for r in parse_ia_search(payload, max_results)]


async def download_internet_archive(
    session: aiohttp.ClientSession,
    identifier: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga el mejor archivo disponible (epub > pdf), probando el siguiente si uno falla."""
    meta = await fetch(session, f"{_METADATA_URL}/{quote(identifier)}", source=SOURCE)
    if not isinstance(meta, dict) or not isinstance(meta.get("files"), list):
        raise BooksApiError("No se encontraron archivos para ese libro en Internet Archive.")

    limit = settings.max_file_size_bytes
    candidates = pick_files(meta["files"], limit)
    if not candidates:
        raise BooksApiError("No se encontró un EPUB o PDF descargable en Internet Archive.")

    metadata = meta.get("metadata")
    title = _first(metadata.get("title")) if isinstance(metadata, dict) else ""
    last_error: BooksApiError | None = None
    for name, ext in candidates[:MAX_FILE_ATTEMPTS]:
        url = f"{_DOWNLOAD_URL}/{quote(identifier)}/{quote(name)}"
        try:
            got = await fetch_book(session, url, source=SOURCE, limit=limit)
        except BooksApiError as e:
            logger.info("internet archive: %s falló (%s), probando siguiente", name, e)
            last_error = e
            continue
        return got.data, f"{safe_filename(title or identifier)}{ext}"
    assert last_error is not None
    raise last_error
