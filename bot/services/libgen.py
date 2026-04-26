"""Integración de búsqueda de libros de Libgen."""

from __future__ import annotations

import asyncio
import html
import hashlib
import logging
import re
from urllib.parse import urlencode, urljoin, urlparse

import aiohttp

from bot.services.books_api import BookResult, BooksApiError

logger = logging.getLogger(__name__)
LIBGEN_HOSTS = (
    "https://libgen.is",
    "https://libgen.rs",
    "https://libgen.st",
    "https://libgen.li",
)
LIBGEN_SEARCH_PATH = "/search.php"


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip())[:80]
    return base or "libro"


def _clean_text(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", "", html_text)
    return html.unescape(text).strip()


def _choose_filename(url: str, metadata_title: str | None = None) -> str:
    parsed = urlparse(url)
    name = None
    if metadata_title:
        name = _safe_filename(metadata_title)
    path_name = parsed.path.rsplit("/", 1)[-1]
    if path_name:
        path_name = path_name.split("?")[0]
        if path_name:
            root, ext = (path_name.rsplit(".", 1) + [""])[:2]
            if ext:
                return f"{_safe_filename(root)}.{ext}"
    if name:
        ext = parsed.path.rsplit(".", 1)[-1] or "bin"
        return f"{name}.{ext}"
    checksum = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
    return f"libro_{checksum}.bin"


def _detect_ext_by_magic(data: bytes) -> str | None:
    if data[:4] == b"%PDF":
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        return "epub"
    if data[:4] in (b"BOOK", b"\x00\x00\x00 "):
        return "mobi"
    return None


def _ext_from_content_type(ctype: str) -> str | None:
    mapping = {
        "application/pdf": "pdf",
        "application/epub+zip": "epub",
        "application/x-mobipocket-ebook": "mobi",
        "application/octet-stream": None,
    }
    return mapping.get(ctype)


async def search_libgen(query: str, max_results: int) -> list[BookResult]:
    params = {
        "req": query,
        "column": "title",
        "view": "simple",
        "phrase": "1",
        "res": str(max(1, max_results)),
    }

    timeout = aiohttp.ClientTimeout(total=20, connect=8)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for host in LIBGEN_HOSTS:
            try:
                async with session.get(
                    f"{host}{LIBGEN_SEARCH_PATH}",
                    params=params,
                    timeout=timeout,
                ) as resp:
                    resp.raise_for_status()
                    payload = await resp.text()
            except asyncio.TimeoutError:
                logger.warning("libgen timeout host=%s, probando siguiente", host)
                continue
            except aiohttp.ClientError as e:
                logger.warning("libgen error host=%s: %s", host, e)
                continue

            results = _parse_libgen_search_html(payload, host, max_results)
            if results:
                return results

    return []


def _parse_libgen_search_html(html_payload: str, host: str, max_results: int) -> list[BookResult]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_payload, flags=re.S | re.I)
    results: list[BookResult] = []
    for row in rows:
        if "<th" in row.lower():
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)
        if len(cells) < 10:
            continue
        title_html = cells[2]
        title = _clean_text(title_html)
        if not title:
            continue
        author = _clean_text(cells[1])
        download_links = re.findall(r'href=["\']([^"\']+)["\']', cells[9])
        if not download_links:
            continue
        download_url = download_links[0]
        if download_url.startswith("/"):
            download_url = urljoin(host, download_url)
        elif not download_url.startswith(("http://", "https://")):
            download_url = urljoin(host, download_url)
        label = f"{title} - {author}" if author else title
        results.append(BookResult(id=download_url, title=label[:500]))
        if len(results) >= max(1, max_results):
            break
    return results


async def download_libgen(
    session: aiohttp.ClientSession,
    book_id: str,
    settings,
) -> tuple[bytes, str]:
    if not book_id.startswith(("http://", "https://")):
        raise BooksApiError("ID de Libgen inválido.")

    limit = settings.max_file_size_bytes
    timeout_page = aiohttp.ClientTimeout(total=20, connect=8)
    timeout_file = aiohttp.ClientTimeout(total=120, connect=10)

    # Paso 1: detectar si es página intermedia o archivo directo
    # Es página intermedia si el dominio es library.lol o similar
    # y la ruta contiene /main/ o /fiction/
    is_intermediate = any(
        domain in book_id
        for domain in ("library.lol", "libgen.lol", "libgen.rocks")
    )

    download_url = book_id
    filename_hint = None

    if is_intermediate:
        # Paso 2: hacer GET a la página intermedia y extraer link real
        try:
            async with session.get(book_id, timeout=timeout_page) as resp:
                resp.raise_for_status()
                html_text = await resp.text(errors="replace")
        except aiohttp.ClientError as e:
            raise BooksApiError("No se pudo acceder a la página de descarga.") from e

        # Extraer href que contiene el archivo real
        # Buscar <a href="https://...get.php..."> o <a id="download" href="...">
        match = re.search(
            r'href=["\']('
            r'https?://[^"\']*(?:get\.php|/get/)[^"\']*'
            r')["\']',
            html_text,
        )
        if not match:
            # Segundo intento: buscar cualquier link de descarga directa
            match = re.search(
                r'<a[^>]+id=["\']download["\'][^>]*href=["\']([^"\']+)["\']',
                html_text,
            )
        if not match:
            raise BooksApiError(
                "No se encontró el link de descarga en la página de Libgen."
            )
        download_url = match.group(1)

    # Paso 3: descargar el archivo real
    try:
        async with session.get(download_url, timeout=timeout_file) as resp:
            resp.raise_for_status()
            content_length = resp.content_length
            if content_length is not None and content_length > limit:
                raise BooksApiError(
                    f"El archivo (~{content_length // (1024*1024)} MB) supera el límite."
                )
            data = await resp.read()
            cd = resp.headers.get("Content-Disposition", "")
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    except aiohttp.ClientError as e:
        raise BooksApiError("No se pudo descargar el libro desde Libgen.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    # Detectar extensión real por magic bytes
    ext = _detect_ext_by_magic(data) or _ext_from_content_type(ctype) or "bin"

    # Nombre desde Content-Disposition o fallback
    filename = None
    if "filename=" in cd:
        part = cd.split("filename=", 1)[1].strip().strip('"').split(";")[0].strip()
        if part:
            filename = part
    if not filename:
        filename = f"{_safe_filename(book_id)}.{ext}"

    return data, filename
