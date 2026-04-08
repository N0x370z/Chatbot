"""Carga y validación de configuración desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    admin_user_id: int
    max_file_size_mb: int
    download_path: Path
    log_level: str

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


def get_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        msg = (
            "Falta TELEGRAM_BOT_TOKEN. Copia .env.example a .env y configura el token."
        )
        raise ValueError(msg)

    admin_raw = os.environ.get("ADMIN_USER_ID", "0").strip()
    admin_user_id = int(admin_raw) if admin_raw else 0

    max_mb_raw = os.environ.get("MAX_FILE_SIZE_MB", "50").strip()
    max_file_size_mb = int(max_mb_raw) if max_mb_raw else 50

    download_str = os.environ.get("DOWNLOAD_PATH", "./downloads").strip() or "./downloads"
    download_path = Path(download_str).resolve()
    download_path.mkdir(parents=True, exist_ok=True)

    log_level = os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO"

    return Settings(
        telegram_bot_token=token,
        admin_user_id=admin_user_id,
        max_file_size_mb=max_file_size_mb,
        download_path=download_path,
        log_level=log_level,
    )
