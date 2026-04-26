"""Conversión de formatos (FFmpeg, Calibre, etc.)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class ConversionError(Exception):
    pass


SUPPORTED_INPUT = {".pdf", ".epub", ".mobi", ".azw", ".azw3", ".docx", ".html", ".txt"}
SUPPORTED_OUTPUT = {"epub", "pdf", "mobi", "azw3", "txt"}


def calibre_available() -> bool:
    return shutil.which("ebook-convert") is not None


async def convert_book(input_path: Path, output_format: str) -> Path:
    if not calibre_available():
        raise ConversionError("ebook-convert no está instalado.")
    if input_path.suffix.lower() not in SUPPORTED_INPUT:
        raise ConversionError(f"Formato de entrada no soportado: {input_path.suffix}")
    if output_format not in SUPPORTED_OUTPUT:
        raise ConversionError(f"Formato de salida no soportado: {output_format}")
    output_path = input_path.with_suffix(f".{output_format}")
    process = await asyncio.create_subprocess_exec(
        "ebook-convert",
        str(input_path),
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        raise ConversionError(f"ebook-convert falló: {err[:300]}")
    if not output_path.exists():
        raise ConversionError("ebook-convert no generó el archivo de salida.")
    return output_path
