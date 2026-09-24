"""Libgen (solo libgen.li; el resto de espejos se retiró por inestabilidad).

Los resultados apuntan a ``ads.php`` (página intermedia) o ``get.php``
(archivo directo). Solo se siguen enlaces de dominios permitidos para que un
resultado manipulado no pueda hacer que el bot descargue de cualquier host.
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import urljoin, urlparse

import aiohttp

from bot.services.base import BookResult, BooksApiError, book_label, safe_filename
from bot.services.http_utils import fetch, fetch_book

logger = logging.getLogger(__name__)

SOURCE = "Libgen"
LIBGEN_HOSTS = ("https://libgen.li",)
_ALLOWED_DOMAINS = ("libgen.li",)
_INTERMEDIATE_MARKERS = ("ads.php", "library.lol", "libgen.lol", "libgen.rocks")
_PAGE_TIMEOUT = aiohttp.ClientTimeout(total=20, connect=8)
_GET_LINK_RE = re.compile(r'href=["\']((?:https?://[^"\']*)?(?:get\.php|/get/)[^"\']*)["\']')
_DOWNLOAD_ID_RE = re.compile(r'<a[^>]+id=["\']download["\'][^>]*href=["\']([^"\']+)["\']')
_EDITION_LINK_RE = re.compile(r'<a[^>]*href=["\']edition\.php[^"\']*["\'][^>]*>(.*?)</a>', re.S | re.I)
_BOOK_EXTENSIONS = {"epub", "pdf", "mobi"}
# libgen.li sirve una página vacía de nginx a User-Agents que no son de navegador.
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}

# Compatibilidad con los tests existentes.
_safe_filename = safe_filename


def _clean_text(html_text: str) -> str:
    # Los atributos title="" de los tooltips contienen <br>; se quitan antes.
    without_attrs = re.sub(r'\s(?:title|data-[\w-]+)="[^"]*"', "", html_text)
    text = re.sub(r"<[^>]+>", " ", without_attrs)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _is_allowed(url: str) -> bool:
    netloc = urlparse(url).netloc
    return any(netloc == d or netloc.endswith("." + d) for d in _ALLOWED_DOMAINS)


def _parse_libgen_search_html(html_payload: str, host: str, max_results: int) -> list[BookResult]:
    results: list[BookResult] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html_payload, flags=re.S | re.I):
        if "<th" in row.lower():
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)
        if len(cells) < 9:
            continue
        # libgen.li: título, autor, editorial, año, idioma, páginas, tamaño,
        # extensión y espejos (el primero es el propio libgen.li).
        edition = _EDITION_LINK_RE.search(cells[0])
        title = _clean_text(edition.group(1) if edition else cells[0])
        links = re.findall(r'href=["\']([^"\']+)["\']', cells[8])
        ext = _clean_text(cells[7]).lower() if len(cells) > 7 else ""
        if not title or not links or (ext and ext not in _BOOK_EXTENSIONS):
            continue
        details = " · ".join(filter(None, (ext, _clean_text(cells[6]))))
        label = book_label(title, _clean_text(cells[1]))
        if details:
            label = f"{label} ({details})"[:500]
        results.append(BookResult(id=urljoin(host, links[0]), title=label))
        if len(results) >= max(1, max_results):
            break
    return results


async def search_libgen(
    session: aiohttp.ClientSession,
    query: str,
    max_results: int,
    settings=None,
) -> list[BookResult]:
    params = {
        "req": query,
        "columns[]": ["t", "a"],  # título y autor
        "objects[]": "f",  # archivos
        "topics[]": ["l", "f"],  # no ficción y ficción
        "res": 25 if max_results <= 25 else 50,
    }
    for host in LIBGEN_HOSTS:
        try:
            page = await fetch(
                session, f"{host}/index.php", source=SOURCE, parse="text",
                params=params, headers=_HEADERS,
            )
        except BooksApiError as e:
            logger.warning("%s no disponible: %s", host, e)
            continue
        results = _parse_libgen_search_html(page, host, max_results)
        if results:
            return results
    return []


async def _resolve_intermediate(session: aiohttp.ClientSession, page_url: str) -> str:
    page = await fetch(
        session, page_url, source=SOURCE, parse="text", headers=_HEADERS, timeout=_PAGE_TIMEOUT
    )
    match = _GET_LINK_RE.search(page) or _DOWNLOAD_ID_RE.search(page)
    if not match:
        raise BooksApiError("No se encontró el link de descarga en la página de Libgen.")
    return urljoin(page_url, match.group(1))


async def download_libgen(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    if not book_id.startswith(("http://", "https://")):
        raise BooksApiError("ID de Libgen inválido.")

    download_url = book_id
    if any(marker in book_id for marker in _INTERMEDIATE_MARKERS):
        if not _is_allowed(book_id):
            raise BooksApiError(f"Dominio intermediario no permitido: {urlparse(book_id).netloc}")
        download_url = await _resolve_intermediate(session, book_id)

    if not _is_allowed(download_url):
        raise BooksApiError(
            f"El dominio de descarga no está permitido: {urlparse(download_url).netloc}"
        )

    got = await fetch_book(
        session, download_url, source=SOURCE, limit=settings.max_file_size_bytes, headers=_HEADERS
    )
    return got.data, got.filename or f"libgen_{safe_filename(urlparse(download_url).query)[:40]}.{got.kind}"
