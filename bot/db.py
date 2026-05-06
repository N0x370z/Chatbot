"""Caché persistente y base de datos local usando SQLite."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS file_cache ("
                "key TEXT PRIMARY KEY, "
                "file_id TEXT NOT NULL"
                ")"
            )

    async def get_file_id(self, key: str) -> str | None:
        def _get() -> str | None:
            with sqlite3.connect(self.path) as conn:
                cur = conn.execute("SELECT file_id FROM file_cache WHERE key = ?", (key,))
                row = cur.fetchone()
                return row[0] if row else None
        return await asyncio.to_thread(_get)

    async def set_file_id(self, key: str, file_id: str) -> None:
        def _set() -> None:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO file_cache (key, file_id) VALUES (?, ?)", 
                    (key, file_id)
                )
        await asyncio.to_thread(_set)
