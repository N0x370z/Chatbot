"""Tests for http_utils."""

import asyncio
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from bot.services.http_utils import _retry_get


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def get(self, url, **kwargs):
        resp = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(resp, Exception):
            raise resp
        return resp

class DummyResponse:
    def __init__(self, status):
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            req_info = Mock()
            req_info.real_url = "http://dummy"
            raise aiohttp.ClientResponseError(req_info, (), status=self.status)


def test_retry_get_success():
    session = DummySession([DummyResponse(200)])
    resp = asyncio.run(_retry_get(session, "http://dummy"))
    assert resp.status == 200
    assert session.call_count == 1


def test_retry_get_4xx():
    session = DummySession([DummyResponse(404)])
    resp = asyncio.run(_retry_get(session, "http://dummy"))
    assert resp.status == 404
    assert session.call_count == 1


def test_retry_get_5xx_retry_success(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    session = DummySession([DummyResponse(500), DummyResponse(200)])
    resp = asyncio.run(_retry_get(session, "http://dummy"))
    assert resp.status == 200
    assert session.call_count == 2


def test_retry_get_5xx_retry_fail(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    session = DummySession([DummyResponse(502), DummyResponse(503), DummyResponse(504)])
    with pytest.raises(aiohttp.ClientResponseError):
        asyncio.run(_retry_get(session, "http://dummy"))
    assert session.call_count == 3


def test_retry_get_timeout_retry_success(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    session = DummySession([TimeoutError(), DummyResponse(200)])
    resp = asyncio.run(_retry_get(session, "http://dummy"))
    assert resp.status == 200
    assert session.call_count == 2
