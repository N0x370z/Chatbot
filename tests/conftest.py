"""Utilidades compartidas por los tests.

``FakeSession`` sustituye a ``aiohttp.ClientSession``: cada ruta asocia un
fragmento de URL con la respuesta (o lista de respuestas, en orden) que debe
devolver. Registra las peticiones en ``session.calls`` para inspeccionarlas.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import aiohttp
import pytest

from bot.config import Settings
from bot.services import http_utils


class _Content:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def iter_chunked(self, size: int):
        for i in range(0, len(self._body), size):
            yield self._body[i : i + size]


class FakeResponse:
    def __init__(self, json=None, *, body: bytes = b"", text: str = "", status: int = 200,
                 headers: dict | None = None, content_length: int | None = None) -> None:
        self._json = json
        self._body = body
        self._text = text
        self.status = status
        self.headers = headers or {}
        self.content_length = content_length
        self.content = _Content(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(Mock(real_url="http://fake"), (), status=self.status)

    async def json(self, content_type=None):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json

    async def text(self, errors="strict"):
        return self._text

    async def read(self):
        return self._body


class FakeSession:
    def __init__(self, routes: dict[str, object] | None = None) -> None:
        self.routes = {k: list(v) if isinstance(v, list) else [v] for k, v in (routes or {}).items()}
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None, **kwargs):
        self.calls.append({"url": url, "params": list(params or []), "headers": headers or {}})
        for fragment, queue in self.routes.items():
            if fragment in url:
                resp = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(resp, BaseException):
                    raise resp
                return resp
        raise AssertionError(f"Petición inesperada: {url}")


def make_settings(**overrides) -> Settings:
    values = dict(
        telegram_bot_token="test_token",
        admin_user_id=123,
        allowed_user_ids=frozenset(),
        max_file_size_mb=50,
        download_path=Path("/tmp"),
        log_level="INFO",
        rate_limit_window_sec=60,
        rate_limit_max_requests=10,
        books_api_base_url="",
        books_api_key="",
        books_api_key_header="Authorization",
        books_api_key_prefix="Bearer",
        books_api_search_path="/search",
        books_api_download_path_template="/download/{id}",
        books_api_query_param="q",
        books_api_timeout_sec=60,
        books_api_max_results=8,
        incoming_files_path=Path("/tmp"),
        max_upload_size_mb=50,
        calibre_library_path=None,
        ssl_verify=True,
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    """Los reintentos no esperan en los tests."""
    monkeypatch.setattr(http_utils, "RETRY_DELAYS", (0, 0))


EPUB = b"PK\x03\x04epub-bytes"
PDF = b"%PDF-1.4 bytes"
