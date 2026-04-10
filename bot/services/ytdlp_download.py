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


def download_best_audio(url: str, settings: Settings) -> Path:
    """MP3/M4A/WebM según lo que entregue la fuente (sin conversión forzada)."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _assert_under_limit(path, settings)
        return path
    except DownloadError:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def download_apple_m4a(url: str, settings: Settings) -> Path:
    """Audio en M4A vía FFmpeg (útil para ecosistema Apple)."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
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
        return path
    except DownloadError:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def download_best_video(url: str, settings: Settings) -> Path:
    """Mejor formato combinado o único que suela ser MP4/WebM."""
    work_dir = _work_dir(settings)
    opts: dict = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(work_dir / "%(title).80B [%(id)s].%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _finalize_path(work_dir, ydl, info)
        _assert_under_limit(path, settings)
        return path
    except DownloadError:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def cleanup_download(path: Path) -> None:
    """Borra el archivo descargado y la carpeta de trabajo (uuid bajo DOWNLOAD_PATH)."""
    try:
        shutil.rmtree(path.parent, ignore_errors=True)
    except OSError:
        pass
