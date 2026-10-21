from __future__ import annotations

import threading
from typing import Any

from ..models.artifact import Artifact
from ..models.message import Message
from ..models.task import Task, TaskState, TaskStatus, now_utc_iso
from .base import BaseTaskStore


class InMemoryTaskStore(BaseTaskStore):
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()

    def create_task(
        self,
        task_id: str,
        context_id: str,
        initial_message: Message | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        with self._lock:
            status = TaskStatus(
                state=TaskState.SUBMITTED,
                message="Task created",
                timestamp=now_utc_iso(),
            )
            history = [initial_message] if initial_message else []
            task = Task(
                id=task_id,
                context_id=context_id,
                status=status,
                history=history,
                artifacts=[],
                metadata=metadata or {},
            )
            self._tasks[task_id] = task
            return task

    def update_status(
        self,
        task_id: str,
        state: TaskState,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskStatus:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise KeyError(f"Task {task_id} not found")
            status = TaskStatus(
                state=state,
                message=message,
                details=details,
                timestamp=now_utc_iso(),
            )
            task.status = status
            return status

    def append_message(self, task_id: str, message: Message) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise KeyError(f"Task {task_id} not found")
            task.history.append(message)

    def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise KeyError(f"Task {task_id} not found")
            task.artifacts.append(artifact)

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(
        self,
        context_id: str | None = None,
        state: TaskState | None = None,
        limit: int = 50,
    ) -> list[Task]:
        with self._lock:
            results = list(self._tasks.values())
            if context_id:
                results = [t for t in results if t.context_id == context_id]
            if state:
                results = [t for t in results if t.status.state == state]
            # Most recent first
            results.reverse()
            return results[:limit]
