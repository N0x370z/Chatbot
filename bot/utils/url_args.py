"""Parseo de argumentos de comando (URLs)."""

from __future__ import annotations

from telegram.ext import ContextTypes


def url_from_message_args(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    if not context.args:
        return None
    candidate = " ".join(context.args).strip()
    if candidate.startswith(("http://", "https://")):
        return candidate
    return None
