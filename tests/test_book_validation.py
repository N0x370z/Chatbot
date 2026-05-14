"""Tests de validación de magic bytes para libros."""

import pytest
from bot.services._book_validation import detect_book_type, validate_book_bytes
from bot.services.books_api import BooksApiError

def test_detect_book_type_pdf():
    data = b"%PDF-1.4\n..."
    assert detect_book_type(data) == "pdf"

def test_detect_book_type_epub():
    data = b"PK\x03\x04\x14\x00\x08\x00..."
    assert detect_book_type(data) == "epub"

def test_detect_book_type_mobi():
    data = b"BOOKMOBI..."
    assert detect_book_type(data) == "mobi"

def test_detect_book_type_unknown():
    data = b"MZ\x90\x00\x03\x00\x00\x00" # Windows PE Executable
    assert detect_book_type(data) is None

def test_validate_book_bytes_success():
    # Should not raise exception
    validate_book_bytes(b"%PDF-1.5")
    validate_book_bytes(b"PK\x03\x04")
    validate_book_bytes(b"BOOKMOBI")

def test_validate_book_bytes_failure():
    with pytest.raises(BooksApiError, match="El archivo descargado no es un PDF/EPUB válido."):
        validate_book_bytes(b"<html><body><h1>Hola</h1></body></html>")
