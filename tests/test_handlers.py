"""Smoke tests del esqueleto."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bot.config import Settings, get_settings


def test_get_settings_requires_token() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            get_settings()


def test_get_settings_loads(tmp_path: Path) -> None:
    dl = tmp_path / "d"
    env = {
        "TELEGRAM_BOT_TOKEN": "dummy-token-for-test",
        "ADMIN_USER_ID": "123",
        "MAX_FILE_SIZE_MB": "25",
        "DOWNLOAD_PATH": str(dl),
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env, clear=True):
        s = get_settings()
    assert isinstance(s, Settings)
    assert s.telegram_bot_token == "dummy-token-for-test"
    assert s.admin_user_id == 123
    assert s.max_file_size_mb == 25
    assert s.max_file_size_bytes == 25 * 1024 * 1024
    assert s.log_level == "DEBUG"
    assert dl.exists()
