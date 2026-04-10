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
    rate_limit_window_sec: int
    rate_limit_max_requests: int
    books_api_base_url: str
    books_api_key: str
    books_api_search_path: str
    books_api_download_path_template: str
    books_api_query_param: str
    books_api_timeout_sec: int
    books_api_max_results: int

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def books_api_enabled(self) -> bool:
        return bool(self.books_api_base_url.strip())


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
    rl_window_raw = os.environ.get("RATE_LIMIT_WINDOW_SEC", "60").strip()
    rate_limit_window_sec = int(rl_window_raw) if rl_window_raw else 60

    rl_max_raw = os.environ.get("RATE_LIMIT_MAX_REQUESTS", "3").strip()
    rate_limit_max_requests = int(rl_max_raw) if rl_max_raw else 3

    books_api_base_url = os.environ.get("BOOKS_API_BASE_URL", "").strip()
    books_api_key = os.environ.get("BOOKS_API_KEY", "").strip()
    books_api_search_path = (
        os.environ.get("BOOKS_API_SEARCH_PATH", "books/search").strip() or "books/search"
    )
    books_api_download_path_template = (
        os.environ.get("BOOKS_API_DOWNLOAD_PATH", "books/{id}/download").strip()
        or "books/{id}/download"
    )
    books_api_query_param = (
        os.environ.get("BOOKS_API_QUERY_PARAM", "q").strip() or "q"
    )
    b_timeout_raw = os.environ.get("BOOKS_API_TIMEOUT_SEC", "60").strip()
    books_api_timeout_sec = int(b_timeout_raw) if b_timeout_raw else 60
    b_max_raw = os.environ.get("BOOKS_API_MAX_RESULTS", "8").strip()
    books_api_max_results = int(b_max_raw) if b_max_raw else 8
    books_api_max_results = max(1, min(books_api_max_results, 10))

    if books_api_base_url and not books_api_base_url.startswith(("http://", "https://")):
        msg = "BOOKS_API_BASE_URL debe empezar por http:// o https://"
        raise ValueError(msg)

    return Settings(
        telegram_bot_token=token,
        admin_user_id=admin_user_id,
        max_file_size_mb=max_file_size_mb,
        download_path=download_path,
        log_level=log_level,
        rate_limit_window_sec=rate_limit_window_sec,
        rate_limit_max_requests=rate_limit_max_requests,
        books_api_base_url=books_api_base_url,
        books_api_key=books_api_key,
        books_api_search_path=books_api_search_path,
        books_api_download_path_template=books_api_download_path_template,
        books_api_query_param=books_api_query_param,
        books_api_timeout_sec=books_api_timeout_sec,
        books_api_max_results=books_api_max_results,
    )
