from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from ..models.message import AudioPart


class AudioStreamBuffer:
    """Buffer for real-time streaming audio chunks (e.g. Opus or PCM frames)."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, format: str = "opus") -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.format = format
        self._queue: asyncio.Queue[AudioPart | None] = asyncio.Queue()
        self._is_closed = False

    def push_chunk(self, data: bytes, is_final: bool = False) -> None:
        if self._is_closed:
            raise RuntimeError("AudioStreamBuffer is closed")
        part = AudioPart.from_bytes(
            data,
            format=self.format,
            sample_rate=self.sample_rate,
            channels=self.channels,
            is_final=is_final,
        )
        self._queue.put_nowait(part)
        if is_final:
            self.close()

    def close(self) -> None:
        if not self._is_closed:
            self._is_closed = True
            self._queue.put_nowait(None)

    async def stream_chunks(self) -> AsyncGenerator[AudioPart, None]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                break
            yield chunk


def chunk_pcm_data(pcm_bytes: bytes, chunk_size_bytes: int = 640) -> list[bytes]:
    """Splits raw 16-bit PCM bytes into 20ms frames (640 bytes for 16kHz mono)."""
    return [pcm_bytes[i : i + chunk_size_bytes] for i in range(0, len(pcm_bytes), chunk_size_bytes)]
