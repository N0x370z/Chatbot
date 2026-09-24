"""Tipos comunes de las fuentes de libros."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BookResult:
    id: str
    title: str


class BooksApiError(Exception):
    """Error con un mensaje apto para mostrarse tal cual al usuario."""


def safe_filename(name: str, *, max_len: int = 80) -> str:
    base = re.sub(r"[^\w\-.]+", "_", name.strip()).strip("_")[:max_len]
    return base or "libro"


def book_label(title: str, author: str = "") -> str:
    title = title.strip() or "Sin título"
    author = author.strip()
    return (f"{title} - {author}" if author else title)[:500]
