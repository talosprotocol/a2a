from __future__ import annotations

from typing import Any

from ..models.artifact import Artifact
from ..models.message import VideoPart


def create_bounding_box_artifact(
    artifact_id: str,
    name: str,
    boxes: list[dict[str, Any]],
    frame_index: int | None = None,
) -> Artifact:
    """Create typed Artifact for vision detection, OCR boundaries, or spatial boxes."""
    data = {
        "frameIndex": frame_index,
        "boxes": boxes,  # Each box: {"label": str, "score": float, "box_2d": [ymin, xmin, ymax, xmax]}
    }
    return Artifact(
        artifact_id=artifact_id,
        name=name,
        mime_type="application/json+bounding-box",
        data=data,
    )


def frame_to_video_part(
    image_bytes: bytes,
    frame_index: int,
    timestamp_offset_ms: float = 0.0,
    format: str = "jpeg_frame",
) -> VideoPart:
    """Wrap raw frame bytes into an A2A VideoPart."""
    return VideoPart.from_frame_bytes(
        data=image_bytes,
        format=format,
        frame_index=frame_index,
        timestamp_offset_ms=timestamp_offset_ms,
    )
