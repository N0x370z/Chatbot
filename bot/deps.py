"""Acceso a dependencias inyectadas en la aplicación (p. ej. Settings)."""

from __future__ import annotations

from telegram.ext import ContextTypes

from bot.config import Settings
from bot.download_queue import DownloadQueue
from bot.state import BotStats, RateLimiter


def settings_from(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    s = context.application.bot_data.get("settings")
    if s is None:
        msg = "bot_data['settings'] no está inicializado. Revisa bot/main.py."
        raise RuntimeError(msg)
    return s


def stats_from(context: ContextTypes.DEFAULT_TYPE) -> BotStats:
    stats = context.application.bot_data.get("stats")
    if stats is None:
        msg = "bot_data['stats'] no está inicializado. Revisa bot/main.py."
        raise RuntimeError(msg)
    return stats


def limiter_from(context: ContextTypes.DEFAULT_TYPE) -> RateLimiter:
    limiter = context.application.bot_data.get("limiter")
    if limiter is None:
        msg = "bot_data['limiter'] no está inicializado. Revisa bot/main.py."
        raise RuntimeError(msg)
    return limiter


def queue_from(context: ContextTypes.DEFAULT_TYPE) -> DownloadQueue:
    queue = context.application.bot_data.get("download_queue")
    if queue is None:
        msg = "bot_data['download_queue'] no está inicializado. Revisa bot/main.py."
        raise RuntimeError(msg)
    return queue
