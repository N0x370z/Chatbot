"""Acceso a dependencias inyectadas en la aplicación (p. ej. Settings)."""

from __future__ import annotations

from telegram.ext import ContextTypes

from bot.config import Settings


def settings_from(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    s = context.application.bot_data.get("settings")
    if s is None:
        msg = "bot_data['settings'] no está inicializado. Revisa bot/main.py."
        raise RuntimeError(msg)
    return s
