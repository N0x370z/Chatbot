"""Tests de seguridad y validación."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram.ext import ApplicationHandlerStop

from bot.main import check_allowed_user
from bot.services.libgen import download_libgen
from bot.services.books_api import BooksApiError


class MockSettings:
    allowed_user_ids = frozenset([123])
    admin_user_id = 1
    max_file_size_bytes = 1000
    ssl_verify = True


def test_check_allowed_user_success():
    update = MagicMock()
    update.effective_user.id = 123
    context = MagicMock()
    context.bot_data = {"settings": MockSettings()}
    
    # Should not raise Exception
    asyncio.run(check_allowed_user(update, context))


def test_check_allowed_user_admin():
    update = MagicMock()
    update.effective_user.id = 1
    context = MagicMock()
    context.bot_data = {"settings": MockSettings()}
    
    # Should not raise Exception
    asyncio.run(check_allowed_user(update, context))


def test_check_allowed_user_rejected():
    update = MagicMock()
    update.effective_user.id = 999
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot_data = {"settings": MockSettings()}
    
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(check_allowed_user(update, context))
        
    update.effective_message.reply_text.assert_called_once_with("No estás autorizado para usar este bot.")


def test_libgen_domain_validation_rejects_subdomain_hijack():
    # Simulate a search result with a hijacked domain
    hijacked_url = "https://libgen.is.attacker.com/get.php?md5=abc"
    
    session = MagicMock()
    
    with pytest.raises(BooksApiError, match="El dominio de descarga no está permitido"):
        asyncio.run(download_libgen(session, hijacked_url, MockSettings()))


def test_libgen_domain_validation_accepts_valid():
    from unittest.mock import patch
    valid_url = "https://libgen.is/get.php?md5=abc"
    
    class DummyResponse:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def raise_for_status(self): pass
        async def read(self): return b"PK\x03\x04 fake epub"
        @property
        def headers(self): return {"Content-Type": "application/epub+zip"}
        @property
        def content_length(self): return 10

    session = MagicMock()
    
    with patch("aiohttp.ClientSession.get", return_value=DummyResponse()):
        data, filename = asyncio.run(download_libgen(session, valid_url, MockSettings()))
        assert data.startswith(b"PK\x03\x04")
