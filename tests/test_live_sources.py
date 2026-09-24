"""Pruebas contra las APIs reales de cada fuente (red necesaria).

Excluidas por defecto; se ejecutan con ``make test-live`` (o
``pytest -m live``) y semanalmente en CI para detectar cuándo una fuente
cambia o deja de funcionar. Cada caso busca y descarga el primer resultado
que se pueda obtener, como haría un usuario.
"""

from __future__ import annotations

import asyncio
import ssl

import aiohttp
import pytest

from bot.services.base import BooksApiError
from bot.services.sources import SOURCES
from tests.conftest import make_settings

pytestmark = pytest.mark.live

# Fuentes que fallan por motivos externos: su fallo no pone el CI en rojo.
KNOWN_BROKEN = {
    "gutenberg": "gutendex.com cae con frecuencia",
    "standard_ebooks": "OPDS requiere Patrons Circle (401)",
}
CASES = [
    pytest.param(
        key, id=key,
        marks=[pytest.mark.xfail(reason=KNOWN_BROKEN[key], strict=False)] if key in KNOWN_BROKEN else [],
    )
    for key in SOURCES
]


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


async def _search_and_download(source_key: str):
    source = SOURCES[source_key]
    query = source.probe_query
    settings = make_settings(max_file_size_mb=50)
    connector = aiohttp.TCPConnector(ssl=_ssl_context())
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "TelegramMediaBot/1.0"}) as session:
        results = await source.search(session, query, 5, settings)
        assert results, f"{source.label} no devolvió resultados para {query!r}"
        errors = []
        for result in results[:3]:
            try:
                return await source.download(session, result.id, settings)
            except BooksApiError as e:
                errors.append(f"{result.title}: {e}")
        pytest.fail(f"{source.label}: ningún resultado descargable:\n" + "\n".join(errors))


@pytest.mark.parametrize("source_key", CASES)
def test_source_search_and_download(source_key):
    data, filename = asyncio.run(asyncio.wait_for(_search_and_download(source_key), timeout=600))
    assert len(data) > 1000
    assert filename.rsplit(".", 1)[-1] in {"epub", "pdf", "mobi"}
