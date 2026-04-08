"""Descarga de archivos desde URLs o integraciones externas."""

from __future__ import annotations

from pathlib import Path

from bot.config import Settings


def download_path_for(prefix: str, settings: Settings) -> Path:
    """Reserva una ruta bajo DOWNLOAD_PATH para una descarga."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in prefix)[:80]
    return settings.download_path / safe
