"""Capa HTTP común para todas las fuentes de libros.

Todas las peticiones pasan por :func:`fetch` (metadatos/búsquedas, con
reintentos) o :func:`fetch_book` (archivos, en streaming con límite de
tamaño). Así los timeouts, reintentos y mensajes de error son iguales en
todas las fuentes y cada servicio solo se ocupa de interpretar la respuesta.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from bot.services._book_validation import detect_book_type
from bot.services.base import BooksApiError, safe_filename

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = aiohttp.ClientTimeout(total=20, connect=8)
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=180, connect=10)
# Espera antes de cada reintento; la cantidad de elementos es el nº de reintentos.
RETRY_DELAYS: tuple[float, ...] = (1, 2)
_CHUNK = 64 * 1024


@dataclass(frozen=True)
class Downloaded:
    data: bytes
    kind: str  # "pdf" | "epub" | "mobi"
    content_type: str
    filename: str | None  # según Content-Disposition, si lo hay

    def filename_or(self, title: str) -> str:
        """Nombre remoto si existe; si no, ``<título>.<tipo detectado>``."""
        return self.filename or f"{safe_filename(title)}.{self.kind}"


def _query_pairs(params: dict | None) -> list[tuple[str, str]] | None:
    """Expande valores lista (``fl[]``, ``columns[]``...) a pares repetidos."""
    if params is None:
        return None
    return [
        (k, str(item))
        for k, v in params.items()
        for item in (v if isinstance(v, (list, tuple)) else [v])
    ]


def _filename_from_disposition(value: str) -> str | None:
    if "filename=" not in value:
        return None
    part = value.split("filename=", 1)[1].split(";")[0].strip().strip('"')
    if not part:
        return None
    root, _, ext = part.rpartition(".")
    if not root or not ext.isalnum():
        return safe_filename(part)
    return f"{safe_filename(root)}.{ext.lower()}"


async def fetch(
    session: aiohttp.ClientSession,
    url: str,
    *,
    source: str,
    parse: Literal["json", "text", "bytes"] = "json",
    params: dict | None = None,
    headers: dict | None = None,
    timeout: aiohttp.ClientTimeout = SEARCH_TIMEOUT,
) -> Any:
    """GET con reintentos ante timeouts, errores de red y HTTP 5xx.

    Los 4xx no se reintentan. Cualquier fallo se traduce a ``BooksApiError``
    con un mensaje que menciona ``source``.
    """
    attempts = len(RETRY_DELAYS) + 1
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            async with session.get(
                url, params=_query_pairs(params), headers=headers, timeout=timeout
            ) as resp:
                resp.raise_for_status()
                if parse == "json":
                    return await resp.json(content_type=None)
                if parse == "text":
                    return await resp.text(errors="replace")
                return await resp.read()
        except aiohttp.ClientResponseError as e:
            if e.status < 500 or last:
                logger.warning("%s: HTTP %s en %s", source, e.status, url)
                raise BooksApiError(f"{source} respondió con error HTTP {e.status}.") from e
        except TimeoutError as e:
            if last:
                logger.warning("%s: timeout en %s", source, url)
                raise BooksApiError(f"{source} tardó demasiado en responder.") from e
        except aiohttp.ClientError as e:
            if last:
                logger.warning("%s: error de red en %s: %s", source, url, e)
                raise BooksApiError(f"No se pudo contactar {source}.") from e
        except ValueError as e:
            logger.warning("%s: respuesta inválida en %s: %s", source, url, e)
            raise BooksApiError(f"{source} devolvió datos inválidos.") from e
        await asyncio.sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


async def fetch_book(
    session: aiohttp.ClientSession,
    url: str,
    *,
    source: str,
    limit: int,
    headers: dict | None = None,
    timeout: aiohttp.ClientTimeout = DOWNLOAD_TIMEOUT,
) -> Downloaded:
    """Descarga un libro en streaming, cortando en cuanto supera ``limit``.

    Valida por magic bytes que sea PDF/EPUB/MOBI.
    """
    too_big = f"El archivo supera el límite de {limit // (1024 * 1024)} MB."
    try:
        async with session.get(url, headers=headers, timeout=timeout) as resp:
            resp.raise_for_status()
            if resp.content_length is not None and resp.content_length > limit:
                raise BooksApiError(too_big)
            buf = bytearray()
            async for chunk in resp.content.iter_chunked(_CHUNK):
                buf.extend(chunk)
                if len(buf) > limit:
                    raise BooksApiError(too_big)
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            filename = _filename_from_disposition(resp.headers.get("Content-Disposition", ""))
    except aiohttp.ClientResponseError as e:
        logger.warning("%s: descarga HTTP %s en %s", source, e.status, url)
        raise BooksApiError(f"{source} rechazó la descarga (HTTP {e.status}).") from e
    except TimeoutError as e:
        logger.warning("%s: timeout descargando %s", source, url)
        raise BooksApiError(f"{source} tardó demasiado en enviar el archivo.") from e
    except aiohttp.ClientError as e:
        logger.warning("%s: error de red descargando %s: %s", source, url, e)
        raise BooksApiError(f"No se pudo descargar el archivo de {source}.") from e

    data = bytes(buf)
    kind = detect_book_type(data)
    if kind is None:
        raise BooksApiError(f"{source} no devolvió un PDF/EPUB válido.")
    return Downloaded(data=data, kind=kind, content_type=content_type, filename=filename)
