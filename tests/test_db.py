"""Tests for the SQLite database."""

import asyncio
from pathlib import Path

import pytest

from bot.db import Database


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "test.sqlite"
    return Database(db_path)

def test_file_cache(temp_db: Database) -> None:
    assert asyncio.run(temp_db.get_file_id("nonexistent")) is None

    asyncio.run(temp_db.set_file_id("key1", "file_abc123"))
    assert asyncio.run(temp_db.get_file_id("key1")) == "file_abc123"

    # Overwrite
    asyncio.run(temp_db.set_file_id("key1", "file_xyz789"))
    assert asyncio.run(temp_db.get_file_id("key1")) == "file_xyz789"

def test_users_and_bans(temp_db: Database) -> None:
    # Initially no users
    assert asyncio.run(temp_db.get_all_users()) == []
    assert not asyncio.run(temp_db.is_banned(111))

    # Add user
    asyncio.run(temp_db.add_user(111))
    asyncio.run(temp_db.add_user(222))
    users = asyncio.run(temp_db.get_all_users())
    assert set(users) == {111, 222}

    # Ban user 111
    asyncio.run(temp_db.set_banned(111, True))
    assert asyncio.run(temp_db.is_banned(111))
    assert not asyncio.run(temp_db.is_banned(222))

    # Banned user should not be in get_all_users
    users = asyncio.run(temp_db.get_all_users())
    assert users == [222]

    # Unban user 111
    asyncio.run(temp_db.set_banned(111, False))
    assert not asyncio.run(temp_db.is_banned(111))
    users = asyncio.run(temp_db.get_all_users())
    assert set(users) == {111, 222}

def test_set_banned_adds_user_if_missing(temp_db: Database) -> None:
    asyncio.run(temp_db.set_banned(333, True))
    assert asyncio.run(temp_db.is_banned(333))

