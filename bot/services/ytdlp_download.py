"""Parte 2 — Descarga de audio/video con yt-dlp (ejecución bloqueante en thread).

Los handlers deben usar asyncio.to_thread() para no bloquear el event loop.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadError

from bot.config import Settings


class DownloadTooLargeError(Exception):
    def __init__(self, path: Path, size: int, limit: int) -> None:
        self.path = path
        self.size = size
        self.limit = limit
        super().__init__(f"{size} > {limit}")


class DownloadQualityError(Exception):
    pass


def _work_dir(settings: Settings) -> Path:
    d = settings.download_path / uuid.uuid4().hex
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pick_largest_media(directory: Path) -> Path:
    skip = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".description", ".vtt", ".srt"}
    files: list[Path] = []
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() not in skip:
            files.append(p)
    if not files:
        for p in directory.rglob("*"):
            if p.is_file():
                files.append(p)
    if not files:
        raise FileNotFoundError("No se generó ningún archivo descargable.")
    return max(files, key=lambda x: x.stat().st_size)


def _finalize_path(work_dir: Path, ydl: yt_dlp.YoutubeDL, info: dict) -> Path:
    if info.get("_type") == "playlist":
        raise ValueError("Por ahora no se admiten listas de reproducción. Usa un enlace a un solo vídeo/pista.")
    rds = info.get("requested_downloads")
    if isinstance(rds, list) and rds:
        last_fp = rds[-1].get("filepath")
        if last_fp:
            return Path(last_fp)
    fp = info.get("filepath")
    if fp:
        return Path(fp)
    prepared = Path(ydl.prepare_filename(info))
    if prepared.exists():
        return prepared
    return _pick_largest_media(work_dir)


def _assert_under_limit(path: Path, settings: Settings) -> None:
    size = path.stat().st_size
    if size > settings.max_file_size_bytes:
        raise DownloadTooLargeError(
            path,
            size,
            settings.max_file_size_bytes,
        )


def _validate_media(path: Path, *, min_bytes: int, min_duration: float | None, info: dict) -> None:
    size = path.stat().st_size
    if size < min_bytes:
        raise DownloadQualityError(
            f"Archivo demasiado pequeño ({size} bytes). Puede estar corrupto."
        )
    duration = info.get("duration")
    if min_duration is not None and duration is not None:
        if float(duration) < min_duration:
            raise DownloadQualityError(
                f"Contenido demasiado corto ({duration:.0f}s). Mínimo {min_duration:.0f}s."
            )


def _make_progress_hook(bot, chat_id, message_id, loop):
    import time
    import asyncio
    last_edit = [time.time()]
    def hook(d: dict):
        if not bot or not chat_id or not message_id or not loop:
            return
        if d.get("status") == "downloading":
            now = time.time()
            if now - last_edit[0] > 10.0:
                last_edit[0] = now
                pct = d.get("_percent_str", "0%").strip()
                try:
                    asyncio.run_coroutine_threadsafe(
                        bot.edit_message_text(f"Descargando... {pct}", chat_id=chat_id, message_id=message_id),
                        loop
                    )
                except Exception:
                    pass
    return hook


def download_best_audio(url: str, settings: Settings, bot=None, chat_id=None, message_id=None, loop=None) -> tuple[Path, Path]:
    """MP3/M4A/WebM según lo que entregue la fuente (sin conversión forzada)."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bestaudio[abr>=128]/bestaudio[ext=opus]/bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "progress_hooks": [_make_progress_hook(bot, chat_id, message_id, loop)],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _validate_media(path, min_bytes=50_000, min_duration=10.0, info=info)
        _assert_under_limit(path, settings)
        return path, work_dir
    except (DownloadError, DownloadQualityError):
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def download_apple_m4a(url: str, settings: Settings, bot=None, chat_id=None, message_id=None, loop=None) -> tuple[Path, Path]:
    """Audio en M4A vía FFmpeg (útil para ecosistema Apple)."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "progress_hooks": [_make_progress_hook(bot, chat_id, message_id, loop)],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            },
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _assert_under_limit(path, settings)
        return path, work_dir
    except DownloadError:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def download_best_video(url: str, settings: Settings, bot=None, chat_id=None, message_id=None, loop=None) -> tuple[Path, Path]:
    """Mejor formato combinado o único que suela ser MP4/WebM."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "18/bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best",
        "merge_output_format": "mp4",
        "prefer_free_formats": False,
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "writethumbnail": False,
        "writeinfojson": False,
        "progress_hooks": [_make_progress_hook(bot, chat_id, message_id, loop)],
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            },
        },
        "postprocessors": [
            {
                "key": "FFmpegMetadataPP",
            },
            {
                "key": "FFmpegVideoRemuxer",
                "preferedformat": "mp4",
            },
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _validate_media(path, min_bytes=500_000, min_duration=5.0, info=info)
        _assert_under_limit(path, settings)
        return path, work_dir
    except (DownloadError, DownloadQualityError):
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def download_audio_format(url: str, settings: Settings, fmt: str, bot=None, chat_id=None, message_id=None, loop=None) -> tuple[Path, Path]:
    VALID_FMTS = {"mp3", "m4a", "opus", "flac", "aac"}
    if fmt not in VALID_FMTS:
        raise ValueError(f"Formato no soportado: {fmt}")
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bestaudio[abr>=128]/bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "writethumbnail": False,
        "writeinfojson": False,
        "progress_hooks": [_make_progress_hook(bot, chat_id, message_id, loop)],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
            },
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _validate_media(path, min_bytes=50_000, min_duration=10.0, info=info)
        _assert_under_limit(path, settings)
        return path, work_dir
    except (DownloadError, DownloadQualityError):
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def cleanup_download(path: Path) -> None:
    """Borra el archivo descargado y la carpeta de trabajo (uuid bajo DOWNLOAD_PATH)."""
    try:
        shutil.rmtree(path.parent, ignore_errors=True)
    except OSError:
        pass
