"""
Example 03: Multimodal Voice & Video Payloads
Demonstrates constructing multimodal A2A messages containing text, chunked audio streams,
and visual keyframe observations with bounding-box metadata.
"""

import asyncio
from a2a import Message, TextPart, AudioPart, VideoPart
from a2a.multimodal.audio import AudioStreamBuffer, chunk_pcm_data
from a2a.multimodal.video import create_bounding_box_artifact, frame_to_video_part


async def main():
    print("--- 1. Constructing Audio Stream Payload ---")
    sample_rate = 16000
    # 100ms of 16-bit PCM silence (3200 bytes)
    pcm_bytes = b"\x00\x00" * int(sample_rate * 0.1)

    # 1a. Chunk raw PCM into 20ms frames (640 bytes each for 16kHz mono)
    pcm_frames = chunk_pcm_data(pcm_bytes, chunk_size_bytes=640)
    print(f"Chunked {len(pcm_bytes)} PCM bytes into {len(pcm_frames)} frames of 20ms each")

    # 1b. Use AudioStreamBuffer to stream chunks asynchronously
    stream_buffer = AudioStreamBuffer(sample_rate=sample_rate, channels=1, format="pcm")
    for frame in pcm_frames[:-1]:
        stream_buffer.push_chunk(frame, is_final=False)
    stream_buffer.push_chunk(pcm_frames[-1], is_final=True)

    streamed_parts = []
    async for audio_chunk in stream_buffer.stream_chunks():
        streamed_parts.append(audio_chunk)
    print(f"Streamed {len(streamed_parts)} AudioParts through AudioStreamBuffer")

    # 1c. Create standalone AudioPart
    audio_part = AudioPart.from_bytes(
        pcm_bytes,
        format="pcm",
        sample_rate=sample_rate,
        channels=1,
    )
    print(f"AudioPart: format={audio_part.format}, sample_rate={audio_part.sample_rate}Hz, length={len(audio_part.chunk_data_b64)} chars base64")

    print("\n--- 2. Constructing Video / Keyframe Payload ---")
    dummy_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
    video_part = frame_to_video_part(
        image_bytes=dummy_jpeg_bytes,
        frame_index=0,
        timestamp_offset_ms=500.0,
    )
    print(f"VideoPart: format={video_part.format}, frame_index={video_part.frame_index}, b64_len={len(video_part.payload_b64)}")

    # Vision bounding box artifact
    boxes = [
        {"label": "visa_table", "score": 0.95, "box_2d": [0.1, 0.1, 0.8, 0.9]}
    ]
    bbox_artifact = create_bounding_box_artifact(
        artifact_id="bbox-001",
        name="Detected Visual Regions",
        boxes=boxes,
        frame_index=0,
    )
    print(f"BoundingBox Artifact: name='{bbox_artifact.name}', mime={bbox_artifact.mime_type}")

    print("\n--- 3. Packaging into Heterogeneous A2A Message ---")
    msg = Message(
        role="user",
        parts=[
            TextPart(text="Transcribe speech and inspect visual table regions."),
            audio_part,
            video_part,
        ],
    )
    print(f"Message assembled with {len(msg.parts)} heterogeneous parts:")
    for idx, part in enumerate(msg.parts):
        print(f"  Part {idx+1}: type={part.type}")

    payload = msg.to_dict()
    print(f"Serialized Message dictionary keys: {list(payload.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
