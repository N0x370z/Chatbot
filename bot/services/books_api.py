"""Cliente HTTP para búsqueda y descarga de libros vía API REST propia.

Contrato esperado (ajústalo a tu backend con las variables de entorno):

Búsqueda — GET ``{BOOKS_API_BASE_URL}{BOOKS_API_SEARCH_PATH}?{BOOKS_API_QUERY_PARAM}=...``

Respuesta JSON con una lista en cualquiera de estas claves:
``results``, ``data``, ``books``, ``items``. Cada elemento es un objeto con
``id`` (o ``book_id``, ``uuid``) y ``title`` (o ``name``, ``label``).

Descarga — GET ``{BOOKS_API_BASE_URL}`` + ruta con ``{id}`` sustituido, p. ej.
``/books/{id}/download``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from aiohttp import ClientResponseError
from yarl import URL

from bot.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookResult:
    id: str
    title: str


class BooksApiError(Exception):
    pass


_LIST_KEYS = ("results", "data", "books", "items")
_ID_KEYS = ("id", "book_id", "uuid")
_TITLE_KEYS = ("title", "name", "label")


def normalize_book_results(payload: Any, *, max_items: int) -> list[BookResult]:
    if not isinstance(payload, dict):
        return []
    items_raw = None
    for key in _LIST_KEYS:
        v = payload.get(key)
        if isinstance(v, list):
            items_raw = v
            break
    if not items_raw:
        return []
    out: list[BookResult] = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        bid = next((it.get(k) for k in _ID_KEYS if it.get(k) is not None), None)
        if bid is None:
            continue
        title = next(
            (str(it.get(k)) for k in _TITLE_KEYS if it.get(k) is not None),
            str(bid),
        )
        out.append(BookResult(id=str(bid), title=title[:500]))
        if len(out) >= max_items:
            break
    return out


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip())[:80]
    return base or "libro"


def _full_request_url(settings: Settings, path: str) -> str:
    p = path.strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    base = settings.books_api_base_url.strip().rstrip("/")
    rel = p.lstrip("/")
    return str(URL(base) / rel)


async def search_books(
    session: aiohttp.ClientSession,
    settings: Settings,
    query: str,
) -> list[BookResult]:
    if not settings.books_api_base_url:
        raise BooksApiError("BOOKS_API_BASE_URL no está configurada.")
    params = {settings.books_api_query_param: query}
    url = _full_request_url(settings, settings.books_api_search_path)
    try:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except ClientResponseError as e:
        logger.warning("books search HTTP %s: %s", e.status, e.message)
        raise BooksApiError(f"La API respondió con error HTTP {e.status}.") from e
    except aiohttp.ClientError as e:
        logger.warning("books search red: %s", e)
        raise BooksApiError("No se pudo contactar la API de libros.") from e
    except ValueError as e:
        raise BooksApiError("La API no devolvió JSON válido.") from e

    return normalize_book_results(data, max_items=settings.books_api_max_results)


async def download_book_bytes(
    session: aiohttp.ClientSession,
    settings: Settings,
    book_id: str,
) -> tuple[bytes, str]:
    if not settings.books_api_base_url:
        raise BooksApiError("BOOKS_API_BASE_URL no está configurada.")
    rel = settings.books_api_download_path_template.format(id=book_id)
    url = _full_request_url(settings, rel)
    limit = settings.max_file_size_bytes
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            cl = resp.content_length
            if cl is not None and cl > limit:
                raise BooksApiError(
                    f"El archivo remoto (~{cl // (1024 * 1024)} MB) supera el límite."
                )
            data = await resp.read()
            cd = resp.headers.get("Content-Disposition", "")
            ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    except ClientResponseError as e:
        logger.warning("books download HTTP %s: %s", e.status, e.message)
        raise BooksApiError(f"Descarga rechazada por la API (HTTP {e.status}).") from e
    except aiohttp.ClientError as e:
        logger.warning("books download red: %s", e)
        raise BooksApiError("No se pudo descargar el libro.") from e

    if len(data) > limit:
        raise BooksApiError("El archivo descargado supera MAX_FILE_SIZE_MB.")

    filename = None
    if "filename=" in cd:
        part = cd.split("filename=", 1)[1].strip().strip('"').split(";")[0].strip()
        if part:
            filename = part
    if not filename:
        ext = {
            "application/pdf": ".pdf",
            "application/epub+zip": ".epub",
            "application/x-mobipocket-ebook": ".mobi",
        }.get(ctype, ".bin")
        filename = f"{_safe_filename(book_id)}{ext}"

    return data, filename
