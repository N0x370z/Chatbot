"""Registro único de fuentes de libros.

Para añadir una fuente basta con implementar ``search``/``download`` en su
módulo y registrarla aquí; el handler, ``/fuente`` y la cadena de respaldo
se generan a partir de este registro.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiohttp

from bot.services.base import BookResult
from bot.services.dbooks import download_dbooks, search_dbooks
from bot.services.gutenberg import download_gutenberg, search_gutenberg
from bot.services.internet_archive import download_internet_archive, search_internet_archive
from bot.services.libgen import download_libgen, search_libgen
from bot.services.open_library import download_open_library, search_open_library
from bot.services.standard_ebooks import download_standard_ebooks, search_standard_ebooks

SearchFn = Callable[[aiohttp.ClientSession, str, int, object], Awaitable[list[BookResult]]]
DownloadFn = Callable[[aiohttp.ClientSession, str, object], Awaitable[tuple[bytes, str]]]


@dataclass(frozen=True)
class BookSource:
    key: str
    label: str
    description: str
    search: SearchFn
    download: DownloadFn


def _no_settings(fn):
    """Adapta ``search(session, q, n)`` a la firma común con ``settings``."""
    return lambda session, query, limit, settings: fn(session, query, limit)


# El orden es la prioridad de la cadena de respaldo: primero las fuentes
# estables y con descarga directa, al final las que suelen fallar.
_ALL = (
    BookSource(
        "open_library", "Open Library", "clásicos de dominio público (vía Internet Archive)",
        _no_settings(search_open_library), download_open_library,
    ),
    BookSource(
        "internet_archive", "Internet Archive", "biblioteca digital con millones de textos",
        _no_settings(search_internet_archive), download_internet_archive,
    ),
    BookSource(
        "dbooks", "dBooks", "libros técnicos y de programación gratuitos",
        _no_settings(search_dbooks), download_dbooks,
    ),
    BookSource(
        "libgen", "Libgen", "catálogo amplio de libros técnicos y académicos",
        search_libgen, download_libgen,
    ),
    BookSource(
        "gutenberg", "Gutenberg", "Project Gutenberg (su API cae con frecuencia)",
        _no_settings(search_gutenberg), download_gutenberg,
    ),
    BookSource(
        "standard_ebooks", "Standard Ebooks", "EPUB cuidados (requiere cuenta de pago)",
        _no_settings(search_standard_ebooks), download_standard_ebooks,
    ),
)

SOURCES: dict[str, BookSource] = {s.key: s for s in _ALL}
DEFAULT_SOURCE = "open_library"
