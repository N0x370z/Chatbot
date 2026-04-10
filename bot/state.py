"""Estado en memoria del bot: métricas simples y rate limit por usuario."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
import time


@dataclass
class BotStats:
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    commands_total: int = 0
    command_counts: Counter[str] = field(default_factory=Counter)
    unique_users: set[int] = field(default_factory=set)
    downloads_ok: int = 0
    downloads_failed: int = 0
    rate_limited_hits: int = 0

    def mark_command(self, command: str, user_id: int | None) -> None:
        self.commands_total += 1
        self.command_counts[command] += 1
        if user_id is not None:
            self.unique_users.add(user_id)

    def mark_download(self, *, ok: bool) -> None:
        if ok:
            self.downloads_ok += 1
        else:
            self.downloads_failed += 1

    def mark_rate_limited(self) -> None:
        self.rate_limited_hits += 1

    def uptime_human(self) -> str:
        delta = datetime.now(UTC) - self.started_at
        total = int(delta.total_seconds())
        hours, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}"


class RateLimiter:
    def __init__(self, *, window_seconds: int, max_requests: int) -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        q = self._events[user_id]
        threshold = now - float(self.window_seconds)
        while q and q[0] < threshold:
            q.popleft()
        if len(q) >= self.max_requests:
            return False
        q.append(now)
        return True
