from __future__ import annotations

import base64
import datetime
from dataclasses import dataclass, field
from typing import Any, Literal


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass
class TextPart:
    type: Literal["text"] = "text"
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextPart:
        return cls(text=str(data.get("text", "")))


@dataclass
class AudioPart:
    type: Literal["audio"] = "audio"
    format: str = "opus"  # "opus", "pcm_16k", "mp3", "wav"
    sample_rate: int = 16000
    channels: int = 1
    chunk_data_b64: str = ""
    is_final: bool = False

    @property
    def raw_bytes(self) -> bytes:
        return base64.b64decode(self.chunk_data_b64.encode("ascii")) if self.chunk_data_b64 else b""

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        format: str = "opus",
        sample_rate: int = 16000,
        channels: int = 1,
        is_final: bool = False,
    ) -> AudioPart:
        b64 = base64.b64encode(data).decode("ascii")
        return cls(
            format=format,
            sample_rate=sample_rate,
            channels=channels,
            chunk_data_b64=b64,
            is_final=is_final,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "audio",
            "format": self.format,
            "sampleRate": self.sample_rate,
            "channels": self.channels,
            "chunkDataB64": self.chunk_data_b64,
            "isFinal": self.is_final,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudioPart:
        return cls(
            format=str(data.get("format", "opus")),
            sample_rate=int(data.get("sampleRate") or data.get("sample_rate", 16000)),
            channels=int(data.get("channels", 1)),
            chunk_data_b64=str(data.get("chunkDataB64") or data.get("chunk_data_b64", "")),
            is_final=bool(data.get("isFinal") or data.get("is_final", False)),
        )


@dataclass
class VideoPart:
    type: Literal["video"] = "video"
    format: str = "jpeg_frame"  # "jpeg_frame", "mp4", "webrtc_sdp"
    frame_index: int = 0
    timestamp_offset_ms: float = 0.0
    payload_b64: str = ""
    annotations: dict[str, Any] = field(default_factory=dict)

    @property
    def raw_bytes(self) -> bytes:
        return base64.b64decode(self.payload_b64.encode("ascii")) if self.payload_b64 else b""

    @classmethod
    def from_frame_bytes(
        cls,
        data: bytes,
        format: str = "jpeg_frame",
        frame_index: int = 0,
        timestamp_offset_ms: float = 0.0,
        annotations: dict[str, Any] | None = None,
    ) -> VideoPart:
        b64 = base64.b64encode(data).decode("ascii")
        return cls(
            format=format,
            frame_index=frame_index,
            timestamp_offset_ms=timestamp_offset_ms,
            payload_b64=b64,
            annotations=annotations or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "video",
            "format": self.format,
            "frameIndex": self.frame_index,
            "timestampOffsetMs": self.timestamp_offset_ms,
            "payloadB64": self.payload_b64,
            "annotations": self.annotations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoPart:
        return cls(
            format=str(data.get("format", "jpeg_frame")),
            frame_index=int(data.get("frameIndex") or data.get("frame_index", 0)),
            timestamp_offset_ms=float(data.get("timestampOffsetMs") or data.get("timestamp_offset_ms", 0.0)),
            payload_b64=str(data.get("payloadB64") or data.get("payload_b64", "")),
            annotations=dict(data.get("annotations", {})),
        )


Part = TextPart | AudioPart | VideoPart | dict[str, Any]


@dataclass
class Message:
    role: Literal["user", "agent", "system"]
    parts: list[Part]
    message_id: str | None = None
    context_id: str | None = None
    created_at: str = field(default_factory=now_utc_iso)

    @classmethod
    def from_text(
        cls,
        text: str,
        role: Literal["user", "agent", "system"] = "user",
        context_id: str | None = None,
    ) -> Message:
        return cls(
            role=role,
            parts=[TextPart(text=text)],
            context_id=context_id,
        )

    @classmethod
    def from_audio(
        cls,
        audio_bytes: bytes,
        role: Literal["user", "agent", "system"] = "user",
        context_id: str | None = None,
        format: str = "opus",
        sample_rate: int = 16000,
    ) -> Message:
        return cls(
            role=role,
            parts=[AudioPart.from_bytes(audio_bytes, format=format, sample_rate=sample_rate, is_final=True)],
            context_id=context_id,
        )

    def get_text(self) -> str:
        texts = []
        for p in self.parts:
            if isinstance(p, dict) and p.get("type") == "text":
                texts.append(str(p.get("text", "")))
            elif isinstance(p, TextPart):
                texts.append(p.text)
        return " ".join(texts).strip()

    def get_text_content(self) -> str:
        return self.get_text()

    def get_audio_parts(self) -> list[AudioPart]:
        return [p for p in self.parts if isinstance(p, AudioPart)]

    def get_video_parts(self) -> list[VideoPart]:
        return [p for p in self.parts if isinstance(p, VideoPart)]

    def to_dict(self) -> dict[str, Any]:
        parts_data = []
        for p in self.parts:
            if hasattr(p, "to_dict"):
                parts_data.append(p.to_dict())
            elif isinstance(p, dict):
                parts_data.append(p)
        data: dict[str, Any] = {
            "role": self.role,
            "parts": parts_data,
            "createdAt": self.created_at,
        }
        if self.message_id:
            data["messageId"] = self.message_id
        if self.context_id:
            data["contextId"] = self.context_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        parts: list[Part] = []
        for p in data.get("parts", []):
            if isinstance(p, dict):
                p_type = p.get("type")
                if p_type == "text":
                    parts.append(TextPart.from_dict(p))
                elif p_type == "audio":
                    parts.append(AudioPart.from_dict(p))
                elif p_type == "video":
                    parts.append(VideoPart.from_dict(p))
                else:
                    parts.append(p)
            elif isinstance(p, (TextPart, AudioPart, VideoPart)):
                parts.append(p)
        return cls(
            role=data.get("role", "user"),
            parts=parts,
            message_id=data.get("messageId") or data.get("message_id"),
            context_id=data.get("contextId") or data.get("context_id"),
            created_at=str(data.get("createdAt") or data.get("created_at") or now_utc_iso()),
        )
