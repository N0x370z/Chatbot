"""Tests para bot/handlers/uploads.py — integridad de archivos y validaciones."""

from __future__ import annotations

import pytest
from pathlib import Path

from bot.handlers.uploads import _is_supported, _safe_name, _verify_file_integrity
from unittest.mock import MagicMock


# ---------- _is_supported ----------

def _doc(file_name=None, mime_type=None):
    d = MagicMock()
    d.file_name = file_name
    d.mime_type = mime_type
    return d


def test_is_supported_pdf_extension():
    assert _is_supported(_doc(file_name="book.pdf")) is True


def test_is_supported_epub_extension():
    assert _is_supported(_doc(file_name="book.epub")) is True


def test_is_supported_pdf_mime():
    assert _is_supported(_doc(mime_type="application/pdf")) is True


def test_is_supported_epub_mime():
    assert _is_supported(_doc(mime_type="application/epub+zip")) is True


def test_is_not_supported():
    assert _is_supported(_doc(file_name="video.mp4", mime_type="video/mp4")) is False


def test_is_not_supported_empty():
    assert _is_supported(_doc()) is False


# ---------- _safe_name ----------

def test_safe_name_normal():
    assert _safe_name("book.pdf", "fallback.pdf") == "book.pdf"


def test_safe_name_with_path():
    # Only the basename should be kept
    assert _safe_name("/etc/passwd", "fallback") == "passwd"


def test_safe_name_empty():
    assert _safe_name("", "fallback.pdf") == "fallback.pdf"


def test_safe_name_none():
    assert _safe_name(None, "fallback.pdf") == "fallback.pdf"


# ---------- _verify_file_integrity ----------

def test_verify_integrity_valid_pdf(tmp_path):
    f = tmp_path / "book.pdf"
    f.write_bytes(b"%PDF-1.4 rest of content")
    assert _verify_file_integrity(f, ".pdf") is True


def test_verify_integrity_invalid_pdf(tmp_path):
    f = tmp_path / "fake.pdf"
    f.write_bytes(b"NOTAPDF")
    assert _verify_file_integrity(f, ".pdf") is False


def test_verify_integrity_valid_epub(tmp_path):
    f = tmp_path / "book.epub"
    f.write_bytes(b"PK\x03\x04 ZIP-based EPUB content")
    assert _verify_file_integrity(f, ".epub") is True


def test_verify_integrity_invalid_epub(tmp_path):
    f = tmp_path / "fake.epub"
    f.write_bytes(b"NOTANEPUB")
    assert _verify_file_integrity(f, ".epub") is False


def test_verify_integrity_missing_file(tmp_path):
    f = tmp_path / "nonexistent.pdf"
    assert _verify_file_integrity(f, ".pdf") is False


def test_verify_integrity_unknown_extension(tmp_path):
    f = tmp_path / "doc.mobi"
    f.write_bytes(b"MOBI content")
    # Unknown extension returns True (no check defined)
    assert _verify_file_integrity(f, ".mobi") is True
