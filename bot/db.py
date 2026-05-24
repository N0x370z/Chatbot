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
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "user_id INTEGER PRIMARY KEY, "
                "banned BOOLEAN DEFAULT 0"
                ")"
            )

    async def add_user(self, user_id: int) -> None:
        def _add():
            with sqlite3.connect(self.path) as conn:
                conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await asyncio.to_thread(_add)

    async def get_all_users(self) -> list[int]:
        def _get():
            with sqlite3.connect(self.path) as conn:
                cur = conn.execute("SELECT user_id FROM users WHERE banned = 0")
                return [row[0] for row in cur.fetchall()]
        return await asyncio.to_thread(_get)

    async def set_banned(self, user_id: int, banned: bool) -> None:
        def _set():
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT INTO users (user_id, banned) VALUES (?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET banned=?",
                    (user_id, int(banned), int(banned))
                )
        await asyncio.to_thread(_set)

    async def is_banned(self, user_id: int) -> bool:
        def _get():
            with sqlite3.connect(self.path) as conn:
                cur = conn.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                return bool(row[0]) if row else False
        return await asyncio.to_thread(_get)

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
