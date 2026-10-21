from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .artifact import Artifact
from .message import Message
from .task import Task, TaskStatus


@dataclass
class TaskStatusUpdateEvent:
    task_id: str
    context_id: str
    status: TaskStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "contextId": self.context_id,
            "status": self.status.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskStatusUpdateEvent:
        return cls(
            task_id=str(data.get("taskId") or data.get("task_id", "")),
            context_id=str(data.get("contextId") or data.get("context_id", "")),
            status=TaskStatus.from_dict(data.get("status") or {}),
        )


@dataclass
class TaskArtifactUpdateEvent:
    task_id: str
    context_id: str
    artifact: Artifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "contextId": self.context_id,
            "artifact": self.artifact.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskArtifactUpdateEvent:
        return cls(
            task_id=str(data.get("taskId") or data.get("task_id", "")),
            context_id=str(data.get("contextId") or data.get("context_id", "")),
            artifact=Artifact.from_dict(data.get("artifact") or {}),
        )


@dataclass
class StreamResponse:
    task: Task | None = None
    message: Message | None = None
    status_update: TaskStatusUpdateEvent | None = None
    artifact_update: TaskArtifactUpdateEvent | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        if self.task:
            res["task"] = self.task.to_dict()
        if self.message:
            res["message"] = self.message.to_dict()
        if self.status_update:
            res["statusUpdate"] = self.status_update.to_dict()
        if self.artifact_update:
            res["artifactUpdate"] = self.artifact_update.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamResponse:
        task = Task.from_dict(data["task"]) if "task" in data else None
        message = Message.from_dict(data["message"]) if "message" in data else None
        status_update = (
            TaskStatusUpdateEvent.from_dict(data["statusUpdate"])
            if "statusUpdate" in data
            else None
        )
        artifact_update = (
            TaskArtifactUpdateEvent.from_dict(data["artifactUpdate"])
            if "artifactUpdate" in data
            else None
        )
        return cls(
            task=task,
            message=message,
            status_update=status_update,
            artifact_update=artifact_update,
        )
