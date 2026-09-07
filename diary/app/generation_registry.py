"""Server-side stream buffer (SPEC 3.3, 5.6): generation runs in a background
task decoupled from the HTTP request, writing SSE-shaped events into an
in-memory buffer. A dropped connection can reconnect and replay from where
it left off instead of regenerating from scratch — the background task keeps
running either way.

In-memory only (not persisted across a server restart) and swept on a lazy
timer, not a background scheduler — this is a personal, single-process app
with no concurrent multi-client load to justify more.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

_EXPIRY_SECONDS = 15 * 60


@dataclass
class BufferedEvent:
    event: str
    data: str


class GenerationBuffer:
    def __init__(self) -> None:
        self.events: list[BufferedEvent] = []
        self.finished = False
        self.created_at = time.monotonic()
        self._new_data = asyncio.Event()

    def append(self, event: str, data: str) -> None:
        self.events.append(BufferedEvent(event, data))
        self._new_data.set()
        self._new_data.clear()

    def mark_finished(self) -> None:
        self.finished = True
        self._new_data.set()
        self._new_data.clear()

    async def wait_for_more(self) -> None:
        await self._new_data.wait()

    @property
    def expired(self) -> bool:
        return self.finished and (time.monotonic() - self.created_at) > _EXPIRY_SECONDS


_GENERATIONS: dict[str, GenerationBuffer] = {}


def create(generation_id: str) -> GenerationBuffer:
    _sweep_expired()
    buffer = GenerationBuffer()
    _GENERATIONS[generation_id] = buffer
    return buffer


def get(generation_id: str) -> GenerationBuffer | None:
    return _GENERATIONS.get(generation_id)


def _sweep_expired() -> None:
    expired_ids = [gid for gid, buf in _GENERATIONS.items() if buf.expired]
    for gid in expired_ids:
        del _GENERATIONS[gid]
