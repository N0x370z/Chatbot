"""Tests para bot/config.py — Settings y get_settings."""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from bot.config import Settings


def _full_settings(**overrides) -> Settings:
    base = dict(
        telegram_bot_token="test_token",
        admin_user_id=1,
        max_file_size_mb=50,
        download_path=Path("/tmp"),
        log_level="INFO",
        rate_limit_window_sec=60,
        rate_limit_max_requests=10,
        books_api_base_url="",
        books_api_key="",
        books_api_search_path="/search",
        books_api_download_path_template="/download/{id}",
        books_api_query_param="q",
        books_api_timeout_sec=60,
        books_api_max_results=5,
        incoming_files_path=Path("/tmp/incoming"),
        max_upload_size_mb=50,
        calibre_library_path=None,
        ssl_verify=True,
    )
    base.update(overrides)
    return Settings(**base)


# ---------- Properties ----------

def test_max_file_size_bytes():
    s = _full_settings(max_file_size_mb=10)
    assert s.max_file_size_bytes == 10 * 1024 * 1024


def test_max_upload_size_bytes():
    s = _full_settings(max_upload_size_mb=20)
    assert s.max_upload_size_bytes == 20 * 1024 * 1024


def test_books_api_enabled_false_when_empty():
    s = _full_settings(books_api_base_url="")
    assert s.books_api_enabled is False


def test_books_api_enabled_true():
    s = _full_settings(books_api_base_url="http://api.example.com")
    assert s.books_api_enabled is True


# ---------- ssl_verify flag ----------

def test_ssl_verify_default():
    s = _full_settings(ssl_verify=True)
    assert s.ssl_verify is True


def test_ssl_verify_false():
    s = _full_settings(ssl_verify=False)
    assert s.ssl_verify is False


# ---------- get_settings errors ----------

def test_get_settings_missing_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    from bot.config import get_settings
    with pytest.raises(ValueError, match="Falta TELEGRAM_BOT_TOKEN"):
        get_settings()


def test_get_settings_invalid_books_api_url(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("BOOKS_API_BASE_URL", "ftp://invalid-scheme")
    from bot.config import get_settings
    with pytest.raises(ValueError, match="BOOKS_API_BASE_URL debe empezar"):
        get_settings()


def test_get_settings_ssl_verify_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("BOOKS_API_BASE_URL", "")
    monkeypatch.setenv("SSL_VERIFY", "false")
    monkeypatch.setenv("DOWNLOAD_PATH", str(tmp_path))
    monkeypatch.setenv("INCOMING_FILES_PATH", str(tmp_path / "inc"))
    from bot.config import get_settings
    s = get_settings()
    assert s.ssl_verify is False


def test_get_settings_ssl_verify_default_true(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("BOOKS_API_BASE_URL", "")
    monkeypatch.delenv("SSL_VERIFY", raising=False)
    monkeypatch.setenv("DOWNLOAD_PATH", str(tmp_path))
    monkeypatch.setenv("INCOMING_FILES_PATH", str(tmp_path / "inc"))
    from bot.config import get_settings
    s = get_settings()
    assert s.ssl_verify is True
