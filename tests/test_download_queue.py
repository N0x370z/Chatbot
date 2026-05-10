"""Tests para el caché de file_id en DownloadQueue."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import Settings
from bot.db import Database
from bot.download_queue import DownloadJob, DownloadQueue
from bot.state import BotStats


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="fake_token",
        admin_user_id=0,
        max_file_size_mb=50,
        download_path=tmp_path,
        log_level="WARNING",
        rate_limit_window_sec=60,
        rate_limit_max_requests=10,
        books_api_base_url="",
        books_api_key="",
        books_api_search_path="books/search",
        books_api_download_path_template="books/{id}/download",
        books_api_query_param="q",
        books_api_timeout_sec=30,
        books_api_max_results=5,
        incoming_files_path=tmp_path,
        max_upload_size_mb=50,
        calibre_library_path=None,
        ssl_verify=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# _cache_key
# ──────────────────────────────────────────────────────────────────────────────

def test_cache_key_includes_kind_format_url(tmp_path: Path):
    stats = BotStats()
    q = DownloadQueue(settings=_make_settings(tmp_path), stats=stats)
    job = DownloadJob(
        id="abc",
        kind="audio",
        url="https://youtu.be/test",
        chat_id=1,
        user_id=1,
        audio_format="mp3",
    )
    key = DownloadQueue._cache_key(job)
    assert "audio" in key
    assert "mp3" in key
    assert "https://youtu.be/test" in key


def test_cache_key_video_differs_from_audio(tmp_path: Path):
    stats = BotStats()
    q = DownloadQueue(settings=_make_settings(tmp_path), stats=stats)
    audio_job = DownloadJob(id="1", kind="audio", url="https://x.com/v", chat_id=1, user_id=1)
    video_job = DownloadJob(id="2", kind="video", url="https://x.com/v", chat_id=1, user_id=1)
    assert DownloadQueue._cache_key(audio_job) != DownloadQueue._cache_key(video_job)


# ──────────────────────────────────────────────────────────────────────────────
# Fast path: cache hit
# ──────────────────────────────────────────────────────────────────────────────

def test_run_job_cache_hit_audio(tmp_path: Path):
    """When a file_id is cached the bot reuses it without re-downloading."""
    stats = BotStats()
    settings = _make_settings(tmp_path)
    q = DownloadQueue(settings=settings, stats=stats)

    db = Database(tmp_path / "test.sqlite")

    job = DownloadJob(
        id="zzz",
        kind="audio",
        url="https://youtu.be/cached",
        chat_id=100,
        user_id=5,
        audio_format="mp3",
    )

    cache_key = DownloadQueue._cache_key(job)
    asyncio.run(db.set_file_id(cache_key, "FAKE_FILE_ID_123"))

    bot = AsyncMock()
    bot.send_audio = AsyncMock()

    application = MagicMock()
    application.bot = bot
    application.bot_data = {"db": db}

    asyncio.run(q._run_job(application, job))

    # Should send via cached file_id, not re-download
    bot.send_audio.assert_called_once()
    call_kwargs = bot.send_audio.call_args[1]
    assert call_kwargs["audio"] == "FAKE_FILE_ID_123"
    assert job.status == "done"


def test_run_job_cache_hit_video(tmp_path: Path):
    """Video cache hit uses send_video with the stored file_id."""
    stats = BotStats()
    settings = _make_settings(tmp_path)
    q = DownloadQueue(settings=settings, stats=stats)

    db = Database(tmp_path / "test.sqlite")

    job = DownloadJob(
        id="www",
        kind="video",
        url="https://youtu.be/cached_video",
        chat_id=100,
        user_id=5,
    )

    cache_key = DownloadQueue._cache_key(job)
    asyncio.run(db.set_file_id(cache_key, "FAKE_VIDEO_ID_456"))

    bot = AsyncMock()
    bot.send_video = AsyncMock()

    application = MagicMock()
    application.bot = bot
    application.bot_data = {"db": db}

    asyncio.run(q._run_job(application, job))

    bot.send_video.assert_called_once()
    call_kwargs = bot.send_video.call_args[1]
    assert call_kwargs["video"] == "FAKE_VIDEO_ID_456"
    assert job.status == "done"


# ──────────────────────────────────────────────────────────────────────────────
# jobs_for_user
# ──────────────────────────────────────────────────────────────────────────────

def test_jobs_for_user_empty(tmp_path: Path):
    q = DownloadQueue(settings=_make_settings(tmp_path), stats=BotStats())
    assert q.jobs_for_user(999) == []


def test_jobs_for_user_returns_only_own_jobs(tmp_path: Path):
    q = DownloadQueue(settings=_make_settings(tmp_path), stats=BotStats())
    j1 = DownloadJob(id="a", kind="audio", url="u1", chat_id=1, user_id=10)
    j2 = DownloadJob(id="b", kind="video", url="u2", chat_id=1, user_id=20)
    q._jobs["a"] = j1
    q._jobs["b"] = j2

    result = q.jobs_for_user(10)
    assert len(result) == 1
    assert result[0].id == "a"
