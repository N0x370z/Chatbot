"""Standard Ebooks (https://standardebooks.org): clásicos en EPUB cuidados.

El catálogo OPDS completo se descarga y se filtra localmente por título o
autor. Desde 2026 el feed OPDS exige cuenta de Patrons Circle (HTTP 401),
por eso esta fuente va última en la cadena de respaldo.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label, safe_filename
from bot.services.http_utils import fetch, fetch_book

SOURCE = "Standard Ebooks"
_OPDS_URL = "https://standardebooks.org/feeds/opds/all"
_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_opds(xml_bytes: bytes, query: str, max_results: int) -> list[BookResult]:
    """Parsea el feed OPDS y filtra por query en título y autor."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise BooksApiError("Standard Ebooks devolvió XML inválido.") from e

    q_lower = query.lower()
    results: list[BookResult] = []
    for entry in root.findall("atom:entry", _NS):
        title = (entry.findtext("atom:title", "", _NS) or "").strip()
        authors = ", ".join(
            (a.findtext("atom:name", "", _NS) or "").strip()
            for a in entry.findall("atom:author", _NS)
        ).strip(", ")
        if q_lower not in f"{title} {authors}".lower():
            continue
        epub_url = next(
            (
                link.get("href", "")
                for link in entry.findall("atom:link", _NS)
                if "epub" in link.get("type", "").lower() and link.get("href")
            ),
            "",
        )
        if not epub_url:
            continue
        # El id es la URL del EPUB (clave única estable).
        results.append(BookResult(id=epub_url, title=book_label(title, authors)))
        if len(results) >= max(1, max_results):
            break
    return results


async def search_standard_ebooks(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
) -> list[BookResult]:
    xml_bytes = await fetch(session, _OPDS_URL, source=SOURCE, parse="bytes")
    return _parse_opds(xml_bytes, query, max_results)


async def download_standard_ebooks(
    session: aiohttp.ClientSession,
    epub_url: str,
    settings,
) -> tuple[bytes, str]:
    got = await fetch_book(
        session,
        epub_url,
        source=SOURCE,
        limit=settings.max_file_size_bytes,
        timeout=aiohttp.ClientTimeout(total=120, connect=10),
    )
    raw_name = epub_url.rstrip("/").split("/")[-1]
    filename = raw_name if raw_name.endswith(".epub") else f"{safe_filename(raw_name)}.epub"
    return got.data, filename
