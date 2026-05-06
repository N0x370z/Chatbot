"""Integración con Standard Ebooks para búsqueda y descarga.

Standard Ebooks provee un catálogo OPDS en:
  https://standardebooks.org/feeds/opds

No requiere clave API. Los archivos son epub3 de alta calidad.
Búsqueda: filtramos el feed por título/autor en el cliente (el catálogo
completo es pequeño: ~750 entradas, cargado en su totalidad de una vez).
"""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET

import aiohttp

from bot.services.books_api import BookResult, BooksApiError

logger = logging.getLogger(__name__)

_OPDS_URL = "https://standardebooks.org/feeds/opds"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/terms/",
}


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip())[:80]
    return base or "libro"


def _text(el: ET.Element | None, tag: str, ns: dict) -> str:
    if el is None:
        return ""
    child = el.find(tag, ns)
    return (child.text or "").strip() if child is not None else ""


def _parse_opds(xml_bytes: bytes, query: str, max_results: int) -> list[BookResult]:
    """Parsea el feed OPDS y filtra por query en título y autor."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise BooksApiError("Standard Ebooks devolvió XML inválido.") from e

    q_lower = query.lower()
    results: list[BookResult] = []

    for entry in root.findall("atom:entry", _NS):
        title = _text(entry, "atom:title", _NS)
        # Authors in OPDS: <author><name>…</name></author>
        authors = [
            (a.find("atom:name", _NS).text or "").strip()
            for a in entry.findall("atom:author", _NS)
            if a.find("atom:name", _NS) is not None
        ]
        author_str = ", ".join(filter(None, authors))

        # Filter locally
        haystack = f"{title} {author_str}".lower()
        if q_lower not in haystack:
            continue

        # Find epub link (type application/epub+zip or application/epub)
        epub_url = ""
        for link in entry.findall("atom:link", _NS):
            ltype = link.get("type", "")
            href = link.get("href", "")
            if "epub" in ltype.lower() and href:
                epub_url = href
                break

        if not epub_url:
            continue

        # id is the epub URL itself (serves as a stable unique key)
        label = f"{title} - {author_str}" if author_str else title
        results.append(BookResult(id=epub_url, title=label[:500]))
        if len(results) >= max(1, max_results):
            break

    return results


async def search_standard_ebooks(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    timeout = aiohttp.ClientTimeout(total=20, connect=8)

    try:
        async with session.get(_OPDS_URL, timeout=timeout) as resp:
            resp.raise_for_status()
            xml_bytes = await resp.read()
    except asyncio.TimeoutError as e:
        logger.warning("standard ebooks timeout: %s", e)
        raise BooksApiError("Standard Ebooks tardó demasiado en responder.") from e
    except aiohttp.ClientError as e:
        logger.warning("standard ebooks client error: %s", e)
        raise BooksApiError("No se pudo contactar Standard Ebooks.") from e

    return _parse_opds(xml_bytes, query, max_results)


async def download_standard_ebooks(
    session: aiohttp.ClientSession,
    epub_url: str,
    settings,
) -> tuple[bytes, str]:
    """Descarga el EPUB usando la URL directa que se guarda como id."""
    limit = settings.max_file_size_bytes
    timeout = aiohttp.ClientTimeout(total=120, connect=10)

    try:
        async with session.get(epub_url, timeout=timeout) as resp:
            resp.raise_for_status()
            cl = resp.content_length
            if cl is not None and cl > limit:
                raise BooksApiError(
                    f"El archivo (~{cl // (1024 * 1024)} MB) supera el límite."
                )
            data = await resp.read()
    except aiohttp.ClientError as e:
        logger.warning("standard ebooks download error: %s", e)
        raise BooksApiError("No se pudo descargar el libro de Standard Ebooks.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    # Derive filename from URL path
    raw_name = epub_url.rstrip("/").split("/")[-1]
    filename = raw_name if raw_name.endswith(".epub") else f"{_safe_filename(raw_name)}.epub"
    return data, filename
