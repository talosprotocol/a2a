from __future__ import annotations

import asyncio
import pytest
from a2a.multimodal import (
    AudioStreamBuffer,
    chunk_pcm_data,
    create_bounding_box_artifact,
    frame_to_video_part,
)


@pytest.mark.asyncio
async def test_audio_stream_buffer():
    buf = AudioStreamBuffer(sample_rate=16000, channels=1, format="opus")

    async def producer():
        buf.push_chunk(b"chunk1")
        await asyncio.sleep(0.01)
        buf.push_chunk(b"chunk2", is_final=True)

    async def consumer():
        chunks = []
        async for c in buf.stream_chunks():
            chunks.append(c.raw_bytes)
        return chunks

    producer_task = asyncio.create_task(producer())
    chunks = await consumer()
    await producer_task

    assert chunks == [b"chunk1", b"chunk2"]


def test_chunk_pcm_data():
    raw_pcm = b"\x00" * 1280  # 40ms of 16kHz mono 16-bit PCM (32000 bytes/sec -> 640 bytes/20ms)
    chunks = chunk_pcm_data(raw_pcm, chunk_size_bytes=640)
    assert len(chunks) == 2
    assert chunks[0] == b"\x00" * 640
    assert chunks[1] == b"\x00" * 640


def test_video_parts_and_bounding_box_artifacts():
    frame_bytes = b"\xff\xd8\xff\xe0"
    part = frame_to_video_part(frame_bytes, frame_index=1, timestamp_offset_ms=33.3)
    assert part.raw_bytes == frame_bytes
    assert part.frame_index == 1
    assert part.timestamp_offset_ms == 33.3

    boxes = [
        {"label": "visa_slot_button", "score": 0.98, "box_2d": [100, 200, 150, 400]},
        {"label": "date_header", "score": 0.94, "box_2d": [50, 200, 80, 500]},
    ]
    art = create_bounding_box_artifact("bbox-1", "Slot Elements Detection", boxes, frame_index=1)
    assert art.artifact_id == "bbox-1"
    assert art.mime_type == "application/json+bounding-box"
    assert art.data["frameIndex"] == 1
    assert len(art.data["boxes"]) == 2
