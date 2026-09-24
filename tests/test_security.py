"""Tests de seguridad y validación."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.main import check_allowed_user


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


# La validación de dominios de Libgen está en test_book_sources.py.
