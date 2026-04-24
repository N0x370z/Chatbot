"""Integración con calibredb."""

from __future__ import annotations

import asyncio
from pathlib import Path


class CalibreError(Exception):
    pass


async def add_to_calibre(path: Path, library_path: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "calibredb",
        "add",
        str(path),
        "--with-library",
        str(library_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    out_text = stdout.decode("utf-8", errors="replace").strip()
    err_text = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        msg = err_text or out_text or "calibredb devolvió error."
        raise CalibreError(msg)
    return out_text
