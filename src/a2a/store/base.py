from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.artifact import Artifact
from ..models.message import Message
from ..models.task import Task, TaskState, TaskStatus


class BaseTaskStore(ABC):
    @abstractmethod
    def create_task(
        self,
        task_id: str,
        context_id: str,
        initial_message: Message | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        pass

    @abstractmethod
    def update_status(
        self,
        task_id: str,
        state: TaskState,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskStatus:
        pass

    @abstractmethod
    def append_message(self, task_id: str, message: Message) -> None:
        pass

    @abstractmethod
    def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None:
        pass

    @abstractmethod
    def list_tasks(
        self,
        context_id: str | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        pass
