"""Envío de archivos locales al chat (audio / video / documento)."""

from __future__ import annotations

from pathlib import Path

from telegram import Bot, InputFile, Message

_TIMEOUT = 600

_AUDIO_EXT = frozenset({".mp3", ".m4a", ".ogg", ".opus", ".flac", ".wav"})
_VIDEO_EXT = frozenset({".mp4", ".webm", ".mov"})


async def reply_with_audio_or_document(message: Message, path: Path) -> None:
    ext = path.suffix.lower()
    title = path.stem[:80]
    with path.open("rb") as f:
        if ext in _AUDIO_EXT:
            await message.reply_audio(
                audio=f,
                title=title,
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )
        else:
            await message.reply_document(
                document=InputFile(f, filename=path.name),
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )


async def reply_with_video_or_document(message: Message, path: Path) -> None:
    ext = path.suffix.lower()
    with path.open("rb") as f:
        if ext in _VIDEO_EXT:
            await message.reply_video(
                video=f,
                supports_streaming=True,
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )
        else:
            await message.reply_document(
                document=InputFile(f, filename=path.name),
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )


async def send_audio_or_document(bot: Bot, *, chat_id: int, path: Path) -> None:
    ext = path.suffix.lower()
    title = path.stem[:80]
    with path.open("rb") as f:
        if ext in _AUDIO_EXT:
            await bot.send_audio(
                chat_id=chat_id,
                audio=f,
                title=title,
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )
        else:
            await bot.send_document(
                chat_id=chat_id,
                document=InputFile(f, filename=path.name),
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )


async def send_video_or_document(bot: Bot, *, chat_id: int, path: Path) -> None:
    ext = path.suffix.lower()
    with path.open("rb") as f:
        if ext in _VIDEO_EXT:
            await bot.send_video(
                chat_id=chat_id,
                video=f,
                supports_streaming=True,
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )
        else:
            await bot.send_document(
                chat_id=chat_id,
                document=InputFile(f, filename=path.name),
                read_timeout=_TIMEOUT,
                write_timeout=_TIMEOUT,
                connect_timeout=60,
            )
