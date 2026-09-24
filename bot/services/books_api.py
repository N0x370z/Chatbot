"""Cliente HTTP para búsqueda y descarga de libros vía API REST propia.

Contrato esperado (ajústalo a tu backend con las variables de entorno):

Búsqueda — GET ``{BOOKS_API_BASE_URL}{BOOKS_API_SEARCH_PATH}?{BOOKS_API_QUERY_PARAM}=...``

Respuesta JSON con una lista en cualquiera de estas claves:
``results``, ``data``, ``books``, ``items``. Cada elemento es un objeto con
``id`` (o ``book_id``, ``uuid``) y ``title`` (o ``name``, ``label``).

Descarga — GET ``{BOOKS_API_BASE_URL}`` + ruta con ``{id}`` sustituido, p. ej.
``/books/{id}/download``.

La clave (``BOOKS_API_KEY``) solo se envía a esta API, nunca a las fuentes
públicas.
"""

from __future__ import annotations

from typing import Any

import aiohttp
from yarl import URL

from bot.config import Settings
from bot.services.base import BookResult, BooksApiError
from bot.services.http_utils import fetch, fetch_book

__all__ = [
    "BookResult",
    "BooksApiError",
    "download_book_bytes",
    "normalize_book_results",
    "search_books",
]

SOURCE = "La API de libros"
_LIST_KEYS = ("results", "data", "books", "items")
_ID_KEYS = ("id", "book_id", "uuid")
_TITLE_KEYS = ("title", "name", "label")


def normalize_book_results(payload: Any, *, max_items: int) -> list[BookResult]:
    if not isinstance(payload, dict):
        return []
    items_raw = next((payload[k] for k in _LIST_KEYS if isinstance(payload.get(k), list)), None)
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


def _full_request_url(settings: Settings, path: str) -> str:
    p = path.strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    base = settings.books_api_base_url.strip().rstrip("/")
    rel = p.lstrip("/")
    return str(URL(base) / rel)


def auth_headers(settings: Settings) -> dict[str, str]:
    if not settings.books_api_key:
        return {}
    prefix = settings.books_api_key_prefix
    value = f"{prefix} {settings.books_api_key}".strip() if prefix else settings.books_api_key
    return {settings.books_api_key_header: value}


def _require_base_url(settings: Settings) -> None:
    if not settings.books_api_base_url:
        raise BooksApiError("BOOKS_API_BASE_URL no está configurada.")


async def search_books(
    session: aiohttp.ClientSession,
    settings: Settings,
    query: str,
) -> list[BookResult]:
    _require_base_url(settings)
    payload = await fetch(
        session,
        _full_request_url(settings, settings.books_api_search_path),
        source=SOURCE,
        params={settings.books_api_query_param: query},
        headers=auth_headers(settings),
        timeout=aiohttp.ClientTimeout(total=settings.books_api_timeout_sec),
    )
    return normalize_book_results(payload, max_items=settings.books_api_max_results)


async def download_book_bytes(
    session: aiohttp.ClientSession,
    settings: Settings,
    book_id: str,
) -> tuple[bytes, str]:
    _require_base_url(settings)
    rel = settings.books_api_download_path_template.format(id=book_id)
    got = await fetch_book(
        session,
        _full_request_url(settings, rel),
        source=SOURCE,
        limit=settings.max_file_size_bytes,
        headers=auth_headers(settings),
    )
    return got.data, got.filename_or(book_id)
