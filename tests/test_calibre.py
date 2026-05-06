"""Tests for calibre integration."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bot.services.calibre import add_to_calibre, CalibreError

def test_add_to_calibre_success():
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"Added book ids: 123", b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        
        result = asyncio.run(add_to_calibre(Path("/tmp/book.pdf"), Path("/tmp/lib")))
        assert result == "Added book ids: 123"
        mock_exec.assert_called_once()

def test_add_to_calibre_failure():
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Error adding book")
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc
        
        with pytest.raises(CalibreError, match="Error adding book"):
            asyncio.run(add_to_calibre(Path("/tmp/book.pdf"), Path("/tmp/lib")))
