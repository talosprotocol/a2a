from __future__ import annotations

import base64
from a2a.models import (
    Artifact,
    AudioPart,
    Message,
    StreamResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
    VideoPart,
)


def test_text_and_task_roundtrip():
    text_part = TextPart(text="Test prompt")
    msg = Message(role="user", parts=[text_part], context_id="ctx-1")
    assert msg.get_text() == "Test prompt"

    task_status = TaskStatus(state=TaskState.WORKING, message="Working", details={"pct": 50})
    artifact = Artifact(artifact_id="art-1", name="Result", mime_type="application/json", data={"val": 1})
    task = Task(id="t-1", context_id="ctx-1", status=task_status, history=[msg], artifacts=[artifact])

    task_dict = task.to_dict()
    restored = Task.from_dict(task_dict)

    assert restored.id == "t-1"
    assert restored.status.state == TaskState.WORKING
    assert len(restored.history) == 1
    assert restored.history[0].get_text() == "Test prompt"
    assert len(restored.artifacts) == 1
    assert restored.artifacts[0].name == "Result"


def test_audio_and_video_multimodal_parts():
    raw_audio = b"\x00\x01\x02\x03\x04\x05"
    audio_part = AudioPart.from_bytes(raw_audio, format="opus", sample_rate=16000, is_final=True)
    assert audio_part.raw_bytes == raw_audio
    assert audio_part.format == "opus"
    assert audio_part.is_final is True

    audio_dict = audio_part.to_dict()
    restored_audio = AudioPart.from_dict(audio_dict)
    assert restored_audio.raw_bytes == raw_audio

    raw_frame = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    video_part = VideoPart.from_frame_bytes(
        raw_frame,
        format="jpeg_frame",
        frame_index=42,
        timestamp_offset_ms=1500.5,
        annotations={"detected": ["person"]},
    )
    assert video_part.raw_bytes == raw_frame
    assert video_part.frame_index == 42
    assert video_part.annotations["detected"] == ["person"]

    multi_msg = Message(
        role="user",
        parts=[
            TextPart(text="Transcribe this:"),
            audio_part,
            video_part,
        ],
    )
    assert multi_msg.get_text() == "Transcribe this:"
    assert len(multi_msg.get_audio_parts()) == 1
    assert len(multi_msg.get_video_parts()) == 1

    msg_dict = multi_msg.to_dict()
    restored_multi = Message.from_dict(msg_dict)
    assert len(restored_multi.get_audio_parts()) == 1
    assert len(restored_multi.get_video_parts()) == 1


def test_stream_response_serialization():
    st = TaskStatus(state=TaskState.WORKING, message="In progress")
    status_ev = TaskStatusUpdateEvent(task_id="t1", context_id="c1", status=st)
    art = Artifact(artifact_id="a1", name="Data", mime_type="text/plain", data="content")
    art_ev = TaskArtifactUpdateEvent(task_id="t1", context_id="c1", artifact=art)
    msg = Message.from_text("Intermediate message")

    resp = StreamResponse(status_update=status_ev, artifact_update=art_ev, message=msg)
    resp_dict = resp.to_dict()

    restored = StreamResponse.from_dict(resp_dict)
    assert restored.status_update is not None
    assert restored.status_update.task_id == "t1"
    assert restored.artifact_update is not None
    assert restored.artifact_update.artifact.name == "Data"
    assert restored.message is not None
    assert restored.message.get_text() == "Intermediate message"
