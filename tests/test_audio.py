"""Tests para handlers de audio."""

import asyncio
from unittest.mock import MagicMock, AsyncMock

from bot.handlers.audio import VALID_AUDIO_FMTS, cmd_formato_audio


def test_valid_audio_fmts_are_unified():
    # Verifica que el conjunto de claves sea exactamente mp3, m4a, opus, flac
    assert set(VALID_AUDIO_FMTS.keys()) == {"mp3", "m4a", "opus", "flac"}


def test_cmd_formato_audio_valid():
    update = MagicMock()
    context = MagicMock()
    context.args = ["opus"]
    context.user_data = {"audio_format": "opus"}
    
    update.effective_message.reply_html = AsyncMock()
    
    asyncio.run(cmd_formato_audio(update, context))
    
    update.effective_message.reply_html.assert_called_once()
    args, _ = update.effective_message.reply_html.call_args
    assert "OPUS" in args[0]
