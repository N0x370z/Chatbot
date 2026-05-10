"""Cola de descargas en segundo plano para audio/video/apple."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from telegram.ext import Application
from yt_dlp.utils import DownloadError

from bot.config import Settings
from bot.db import Database
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

log = logging.getLogger(__name__)

JobKind = Literal["audio", "apple", "video"]
JobStatus = Literal["queued", "running", "done", "failed"]

# Máximo de reintentos para errores de red (DownloadError transitorio)
_MAX_RETRIES = 3


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
    retry_count: int = 0          # cuántos reintentos se han realizado


class DownloadQueue:
    def __init__(self, *, settings: Settings, stats: BotStats) -> None:
        self.settings = settings
        self.stats = stats
        self._queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self._jobs: dict[str, DownloadJob] = {}
        self._worker_task: asyncio.Task[None] | None = None

    @staticmethod
    def _cache_key(job: DownloadJob) -> str:
        """Clave única para cachear el file_id en la DB."""
        return f"media:{job.kind}:{job.audio_format}:{job.url}"

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

    # ──────────────────────────────────────────────────────────────────────────
    # Descarga atómica (un único intento; lanza en error)
    # ──────────────────────────────────────────────────────────────────────────

    async def _do_download(
        self,
        application: Application,
        job: DownloadJob,
        db: Database | None,
        cache_key: str,
    ) -> None:
        """Realiza la descarga y el envío. Limpia archivos temporales al salir."""
        bot = application.bot
        path = None
        work_dir = None
        try:
            loop = asyncio.get_running_loop()
            if job.kind in ("audio", "apple"):
                msg = await bot.send_message(chat_id=job.chat_id, text="⏳ Preparando descarga...")
                if job.kind == "apple":
                    path, work_dir = await asyncio.to_thread(
                        download_apple_m4a, job.url, self.settings,
                        bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop,
                    )
                elif job.audio_format in {"m4a", "opus", "flac", "aac"}:
                    path, work_dir = await asyncio.to_thread(
                        download_audio_format, job.url, self.settings, job.audio_format,
                        bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop,
                    )
                else:
                    path, work_dir = await asyncio.to_thread(
                        download_best_audio, job.url, self.settings,
                        bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop,
                    )
                await bot.delete_message(chat_id=job.chat_id, message_id=msg.message_id)
                sent = await send_audio_or_document(bot, chat_id=job.chat_id, path=path)
                if db is not None and sent is not None:
                    fid = getattr(sent.audio, "file_id", None) or getattr(sent.document, "file_id", None)
                    if fid:
                        await db.set_file_id(cache_key, fid)
            else:
                msg = await bot.send_message(chat_id=job.chat_id, text="⏳ Preparando descarga...")
                path, work_dir = await asyncio.to_thread(
                    download_best_video, job.url, self.settings,
                    bot=bot, chat_id=job.chat_id, message_id=msg.message_id, loop=loop,
                )
                await bot.delete_message(chat_id=job.chat_id, message_id=msg.message_id)
                sent = await send_video_or_document(bot, chat_id=job.chat_id, path=path)
                if db is not None and sent is not None:
                    fid = getattr(sent.video, "file_id", None) or getattr(sent.document, "file_id", None)
                    if fid:
                        await db.set_file_id(cache_key, fid)
        finally:
            if work_dir is not None and work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
            if path is not None and path.exists():
                cleanup_download(path)

    # ──────────────────────────────────────────────────────────────────────────
    # Orquestador: caché + reintentos con backoff exponencial
    # ──────────────────────────────────────────────────────────────────────────

    async def _run_job(self, application: Application, job: DownloadJob) -> None:
        bot = application.bot
        db: Database | None = application.bot_data.get("db")
        job.status = "running"
        job.started_at = datetime.now(UTC)
        cache_key = self._cache_key(job)

        # ── Fast path: file_id cacheado ──────────────────────────────────────
        if db is not None:
            cached_fid = await db.get_file_id(cache_key)
            if cached_fid:
                try:
                    if job.kind == "video":
                        await bot.send_video(
                            chat_id=job.chat_id,
                            video=cached_fid,
                            supports_streaming=True,
                        )
                    else:
                        await bot.send_audio(chat_id=job.chat_id, audio=cached_fid)
                    job.status = "done"
                    job.finished_at = datetime.now(UTC)
                    self.stats.mark_download(ok=True)
                    log.debug("Cache hit para job %s (%s)", job.id, cache_key)
                    return
                except Exception as exc:
                    log.warning("Cache hit falló para %s: %s — descargando", cache_key, exc)

        # ── Descarga con reintentos ───────────────────────────────────────────
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = 2 ** (attempt - 1)   # 1s → 2s → 4s
                log.info(
                    "Job %s: reintento %d/%d en %ds",
                    job.id, attempt, _MAX_RETRIES, delay,
                )
                job.retry_count = attempt
                await asyncio.sleep(delay)

            try:
                await self._do_download(application, job, db, cache_key)
                job.status = "done"
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=True)
                return

            except DownloadTooLargeError:
                job.status = "failed"
                job.error = f"Archivo supera {self.settings.max_file_size_mb} MB."
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=False)
                await bot.send_message(chat_id=job.chat_id, text=job.error)
                return

            except DownloadQualityError as exc:
                job.status = "failed"
                job.error = str(exc)[:400]
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=False)
                await bot.send_message(chat_id=job.chat_id, text=f"Error de calidad: {exc}")
                return

            except ValueError as exc:
                job.status = "failed"
                job.error = str(exc)[:400]
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=False)
                await bot.send_message(chat_id=job.chat_id, text=f"Error: {exc}")
                return

            except OSError:
                job.status = "failed"
                job.error = "Error al enviar archivo."
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=False)
                await bot.send_message(chat_id=job.chat_id, text=job.error)
                return

            except DownloadError as exc:
                raw = str(exc)[:300]
                log.warning(
                    "Job %s intento %d/%d falló (DownloadError): %s",
                    job.id, attempt + 1, _MAX_RETRIES + 1, raw,
                )
                if attempt < _MAX_RETRIES:
                    continue   # reintenta

                # Último intento agotado
                job.status = "failed"
                job.error = raw[:400]
                job.finished_at = datetime.now(UTC)
                self.stats.mark_download(ok=False)

                if "ffmpeg" in raw.lower():
                    user_msg = "FFmpeg no está instalado. Instálalo: brew install ffmpeg"
                elif "unsupported url" in raw.lower():
                    user_msg = "URL no soportada. Usa YouTube, SoundCloud o Bandcamp."
                elif "private" in raw.lower():
                    user_msg = "Video privado o con restricción de región."
                elif "copyright" in raw.lower():
                    user_msg = "Video bloqueado por copyright."
                else:
                    user_msg = (
                        f"Descarga fallida tras {_MAX_RETRIES + 1} intentos.\n"
                        f"Error: {raw}"
                    )
                await bot.send_message(chat_id=job.chat_id, text=user_msg)
