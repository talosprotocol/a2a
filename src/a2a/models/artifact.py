from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass
class Artifact:
    artifact_id: str
    name: str
    mime_type: str
    data: Any
    created_at: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactId": self.artifact_id,
            "name": self.name,
            "mimeType": self.mime_type,
            "data": self.data,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return cls(
            artifact_id=str(data.get("artifactId") or data.get("artifact_id", "")),
            name=str(data.get("name", "")),
            mime_type=str(data.get("mimeType") or data.get("mime_type", "application/octet-stream")),
            data=data.get("data"),
            created_at=str(data.get("createdAt") or data.get("created_at") or now_utc_iso()),
        )
