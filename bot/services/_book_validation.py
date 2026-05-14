"""Validación de tipo de archivo por magic bytes.

Uso:
    from bot.services._book_validation import validate_book_bytes
    validate_book_bytes(data)   # lanza BooksApiError si no es PDF/EPUB/MOBI
"""

from __future__ import annotations

from bot.services.books_api import BooksApiError


def detect_book_type(data: bytes) -> str | None:
    """Detecta el tipo de libro por magic bytes.

    Returns "pdf" | "epub" | "mobi" | None
    """
    if data[:4] == b"%PDF":
        return "pdf"
    # EPUB: ZIP archive (PK\x03\x04)
    if data[:4] == b"PK\x03\x04":
        return "epub"
    # MOBI/PalmDB: starts with "BOOK" or the Palm record header (0x00000020)
    if data[:4] == b"BOOK" or data[:4] == b"\x00\x00\x00\x20":
        return "mobi"
    return None


def validate_book_bytes(data: bytes) -> str:
    """Valida que *data* sea un PDF, EPUB o MOBI.

    Returns the detected type string.
    Raises BooksApiError si el contenido no es reconocido.
    """
    book_type = detect_book_type(data)
    if book_type is None:
        raise BooksApiError(
            "El archivo descargado no es un PDF/EPUB válido."
        )
    return book_type
