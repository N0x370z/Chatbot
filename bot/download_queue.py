"""Cola de descargas en segundo plano para audio/video/apple."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from telegram.constants import ChatAction
from telegram.ext import Application
from yt_dlp.utils import DownloadError

from bot.config import Settings
from bot.services.ytdlp_download import (
    DownloadTooLargeError,
    cleanup_download,
    download_apple_m4a,
    download_best_audio,
    download_best_video,
)
from bot.state import BotStats
from bot.utils.telegram_upload import (
    send_audio_or_document,
    send_video_or_document,
)

JobKind = Literal["audio", "apple", "video"]
JobStatus = Literal["queued", "running", "done", "failed"]


@dataclass
class DownloadJob:
    id: str
    kind: JobKind
    url: str
    chat_id: int
    user_id: int
    status: JobStatus = "queued"
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DownloadQueue:
    def __init__(self, *, settings: Settings, stats: BotStats) -> None:
        self.settings = settings
        self.stats = stats
        self._queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self._jobs: dict[str, DownloadJob] = {}
        self._worker_task: asyncio.Task[None] | None = None

    def ensure_started(self, application: Application) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = application.create_task(self._worker(application))

    async def enqueue(
        self,
        application: Application,
        *,
        kind: JobKind,
        url: str,
        chat_id: int,
        user_id: int,
    ) -> DownloadJob:
        self.ensure_started(application)
        job = DownloadJob(
            id=uuid4().hex[:8],
            kind=kind,
            url=url,
            chat_id=chat_id,
            user_id=user_id,
        )
        self._jobs[job.id] = job
        await self._queue.put(job)
        return job

    def jobs_for_user(self, user_id: int, *, limit: int = 8) -> list[DownloadJob]:
        jobs = [j for j in self._jobs.values() if j.user_id == user_id]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def _worker(self, application: Application) -> None:
        while True:
            job = await self._queue.get()
            await self._run_job(application, job)
            self._queue.task_done()

    async def _run_job(self, application: Application, job: DownloadJob) -> None:
        bot = application.bot
        job.status = "running"
        job.started_at = datetime.now(UTC)
        path = None
        try:
            if job.kind in ("audio", "apple"):
                await bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.UPLOAD_VOICE)
                fn = download_apple_m4a if job.kind == "apple" else download_best_audio
                path = await asyncio.to_thread(fn, job.url, self.settings)
                await send_audio_or_document(bot, chat_id=job.chat_id, path=path)
            else:
                await bot.send_chat_action(chat_id=job.chat_id, action=ChatAction.UPLOAD_VIDEO)
                path = await asyncio.to_thread(download_best_video, job.url, self.settings)
                await send_video_or_document(bot, chat_id=job.chat_id, path=path)

            job.status = "done"
            self.stats.mark_download(ok=True)
        except DownloadTooLargeError:
            job.status = "failed"
            job.error = f"Archivo supera {self.settings.max_file_size_mb} MB."
            self.stats.mark_download(ok=False)
            await bot.send_message(chat_id=job.chat_id, text=job.error)
        except (DownloadError, ValueError) as exc:
            job.status = "failed"
            job.error = str(exc)[:400]
            self.stats.mark_download(ok=False)
            await bot.send_message(
                chat_id=job.chat_id,
                text="Descarga fallida. Revisa la URL y FFmpeg.",
            )
        except OSError:
            job.status = "failed"
            job.error = "Error al enviar archivo."
            self.stats.mark_download(ok=False)
            await bot.send_message(chat_id=job.chat_id, text=job.error)
        finally:
            job.finished_at = datetime.now(UTC)
            if path is not None and path.exists():
                cleanup_download(path)
