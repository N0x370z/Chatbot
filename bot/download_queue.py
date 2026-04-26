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
    DownloadQualityError,
    DownloadTooLargeError,
    cleanup_download,
    download_apple_m4a,
    download_audio_format,
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
    audio_format: str = "mp3"


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
        audio_format: str = "mp3",
    ) -> DownloadJob:
        self.ensure_started(application)
        job = DownloadJob(
            id=uuid4().hex[:8],
            kind=kind,
            url=url,
            chat_id=chat_id,
            user_id=user_id,
            audio_format=audio_format,
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
            if job.status != "failed":
                await self._run_job(application, job)
            self._queue.task_done()

    async def _run_job(self, application: Application, job: DownloadJob) -> None:
        bot = application.bot
        job.status = "running"
        job.started_at = datetime.now(UTC)
        path = None
        work_dir = None
        
        try:
            loop = asyncio.get_running_loop()
            if job.kind in ("audio", "apple"):
                msg = await bot.send_message(chat_id=job.chat_id, text="Preparando descarga...")
                if job.kind == "apple":
                    fn = download_apple_m4a
                    path, work_dir = await asyncio.to_thread(fn, job.url, self.settings, bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop)
                elif job.audio_format in {"m4a", "opus", "flac", "aac"}:
                    path, work_dir = await asyncio.to_thread(
                        download_audio_format, job.url, self.settings, job.audio_format, bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop
                    )
                else:
                    path, work_dir = await asyncio.to_thread(download_best_audio, job.url, self.settings, bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop)
                await bot.delete_message(chat_id=job.chat_id, message_id=msg.message_id)
                await send_audio_or_document(bot, chat_id=job.chat_id, path=path)
            else:
                msg = await bot.send_message(chat_id=job.chat_id, text="Preparando descarga...")
                path, work_dir = await asyncio.to_thread(download_best_video, job.url, self.settings, bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop)
                await bot.delete_message(chat_id=job.chat_id, message_id=msg.message_id)
                await send_video_or_document(bot, chat_id=job.chat_id, path=path)

            job.status = "done"
            self.stats.mark_download(ok=True)
        except DownloadTooLargeError:
            job.status = "failed"
            job.error = f"Archivo supera {self.settings.max_file_size_mb} MB."
            self.stats.mark_download(ok=False)
            await bot.send_message(chat_id=job.chat_id, text=job.error)
        except DownloadQualityError as exc:
            job.status = "failed"
            job.error = str(exc)[:400]
            self.stats.mark_download(ok=False)
            await bot.send_message(chat_id=job.chat_id, text=f"Error de calidad: {exc}")
        except (DownloadError, ValueError) as exc:
            job.status = "failed"
            job.error = str(exc)[:400]
            self.stats.mark_download(ok=False)
            msg = str(exc)[:300]
            if "ffmpeg" in msg.lower():
                user_msg = "FFmpeg no está instalado. Instálalo con: brew install ffmpeg (Mac) o sudo apt install ffmpeg (Linux)"
            elif "unsupported url" in msg.lower():
                user_msg = "URL no soportada. Usa YouTube, SoundCloud o Bandcamp."
            elif "private" in msg.lower():
                user_msg = "Video privado o con restricción de región."
            elif "copyright" in msg.lower():
                user_msg = "Video bloqueado por copyright."
            else:
                user_msg = f"Descarga fallida: {msg}"
            await bot.send_message(chat_id=job.chat_id, text=user_msg)
        except OSError:
            job.status = "failed"
            job.error = "Error al enviar archivo."
            self.stats.mark_download(ok=False)
            await bot.send_message(chat_id=job.chat_id, text=job.error)
        finally:
            job.finished_at = datetime.now(UTC)
            if work_dir is not None and work_dir.exists():
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            if path is not None and path.exists():
                cleanup_download(path)
