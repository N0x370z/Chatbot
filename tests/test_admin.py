"""Tests for bot/handlers/admin.py"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram import Update

from bot.handlers.admin import register

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_message = AsyncMock()
    return update

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.args = []
    context.application = MagicMock()
    context.application.bot_data = {}
    context.bot = AsyncMock()
    return context

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_all_users.return_value = [111, 222]
    return db

def test_cmd_ban_not_admin(mock_update, mock_context):
    mock_update.effective_user.id = 999
    # We must extract the handler from register
    app = MagicMock()
    register(app, admin_user_id=123)
    # Get the registered handlers
    ban_handler = next(h for h in app.add_handler.call_args_list if h[0][0].commands == frozenset({'ban'}))[0][0].callback
    
    asyncio.run(ban_handler(mock_update, mock_context))
    mock_update.effective_message.reply_text.assert_not_called()

def test_cmd_ban_admin_success(mock_update, mock_context, mock_db):
    mock_update.effective_user.id = 123
    mock_context.args = ["456"]
    mock_context.application.bot_data["db"] = mock_db
    
    app = MagicMock()
    register(app, admin_user_id=123)
    ban_handler = next(h for h in app.add_handler.call_args_list if h[0][0].commands == frozenset({'ban'}))[0][0].callback
    
    asyncio.run(ban_handler(mock_update, mock_context))
    mock_db.set_banned.assert_called_once_with(456, True)
    mock_update.effective_message.reply_text.assert_called_with("Usuario 456 ha sido baneado.")

def test_cmd_unban_admin_success(mock_update, mock_context, mock_db):
    mock_update.effective_user.id = 123
    mock_context.args = ["456"]
    mock_context.application.bot_data["db"] = mock_db
    
    app = MagicMock()
    register(app, admin_user_id=123)
    unban_handler = next(h for h in app.add_handler.call_args_list if h[0][0].commands == frozenset({'unban'}))[0][0].callback
    
    asyncio.run(unban_handler(mock_update, mock_context))
    mock_db.set_banned.assert_called_once_with(456, False)
    mock_update.effective_message.reply_text.assert_called_with("Usuario 456 ha sido desbaneado.")

def test_cmd_broadcast_admin_success(mock_update, mock_context, mock_db):
    mock_update.effective_user.id = 123
    mock_context.args = ["Hola", "mundo"]
    mock_context.application.bot_data["db"] = mock_db
    
    app = MagicMock()
    register(app, admin_user_id=123)
    broadcast_handler = next(h for h in app.add_handler.call_args_list if h[0][0].commands == frozenset({'broadcast'}))[0][0].callback
    
    asyncio.run(broadcast_handler(mock_update, mock_context))
    
    assert mock_context.bot.send_message.call_count == 2
    mock_update.effective_message.reply_text.assert_any_call("Enviando broadcast...")
    mock_update.effective_message.reply_text.assert_any_call("Broadcast enviado a 2 usuarios de 2.")
