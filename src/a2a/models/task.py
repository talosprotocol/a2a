from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from .artifact import Artifact
from .message import Message


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TaskState(str, Enum):
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    WAITING_INPUT = "TASK_STATE_WAITING_INPUT"

    @classmethod
    def from_str(cls, value: str) -> TaskState:
        val = value.upper()
        if not val.startswith("TASK_STATE_"):
            val = f"TASK_STATE_{val}"
        try:
            return cls(val)
        except ValueError:
            return cls.WORKING


@dataclass
class TaskStatus:
    state: TaskState
    message: str | None = None
    details: dict[str, Any] | None = None
    timestamp: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "state": self.state.value,
            "timestamp": self.timestamp,
        }
        if self.message:
            d["message"] = self.message
        if self.details:
            d["details"] = self.details
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskStatus:
        return cls(
            state=TaskState.from_str(str(data.get("state", "TASK_STATE_WORKING"))),
            message=data.get("message"),
            details=data.get("details"),
            timestamp=str(data.get("timestamp") or now_utc_iso()),
        )


@dataclass
class Task:
    id: str
    context_id: str
    status: TaskStatus
    history: list[Message] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latest_message(self) -> Message | None:
        return self.history[-1] if self.history else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "contextId": self.context_id,
            "status": self.status.to_dict(),
            "history": [m.to_dict() for m in self.history],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            id=str(data.get("id", "")),
            context_id=str(data.get("contextId") or data.get("context_id", "default")),
            status=TaskStatus.from_dict(data.get("status") or {}),
            history=[Message.from_dict(m) for m in data.get("history", [])],
            artifacts=[Artifact.from_dict(a) for a in data.get("artifacts", [])],
            metadata=dict(data.get("metadata", {})),
        )
