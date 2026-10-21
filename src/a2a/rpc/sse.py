from __future__ import annotations

import json
from typing import AsyncGenerator

from ..models.events import StreamResponse


def format_sse_event(response: StreamResponse, event_type: str = "stream_event") -> str:
    """Format a StreamResponse dataclass into a canonical SSE text frame."""
    payload = json.dumps(response.to_dict())
    return f"event: {event_type}\ndata: {payload}\n\n"


async def sse_response_generator(
    stream: AsyncGenerator[StreamResponse, None],
) -> AsyncGenerator[str, None]:
    """Wraps an async generator of StreamResponse into raw SSE string chunks."""
    async for item in stream:
        yield format_sse_event(item)
