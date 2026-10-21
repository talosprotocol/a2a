from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Awaitable, Callable

from ..models.artifact import Artifact
from ..models.events import StreamResponse
from ..models.message import Message
from ..models.task import Task, TaskState

TaskExecutionHandler = Callable[
    [Task, Callable[[str, dict[str, Any] | None], Awaitable[None]], Callable[[], bool]],
    Awaitable[tuple[str, list[Artifact]]],
]


class BaseTaskRunner(ABC):
    @abstractmethod
    async def execute_immediate(
        self,
        context_id: str,
        message: Message,
        handler: TaskExecutionHandler,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> tuple[Task, Message]:
        """Synchronously execute task to completion and return (Task, Message)."""
        pass

    @abstractmethod
    async def submit_task(
        self,
        context_id: str,
        message: Message,
        handler: TaskExecutionHandler,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
        execution_timeout: float = 180.0,
    ) -> Task:
        """Asynchronously submit task and return initial Task record.

        Args:
            execution_timeout: Hard ceiling in seconds before the background task
                is automatically transitioned to FAILED with error code
                ``TASK_EXECUTION_TIMEOUT``.  Defaults to 180 s.
        """
        pass

    @abstractmethod
    async def subscribe_task(self, task_id: str) -> AsyncGenerator[StreamResponse, None]:
        """A2A Task Stream: Yield stream events until task reaches a terminal state."""
        pass

    @abstractmethod
    async def wait_task(self, task_id: str, timeout: float = 180.0) -> Task | None:
        """A2A Task Wait: Await task completion barrier."""
        pass

    @abstractmethod
    def cancel_task(self, task_id: str, reason: str = "Canceled by user") -> bool:
        """A2A Task Cancel: Cooperatively signal cancellation."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None:
        """A2A Task Get: Non-blocking inspection."""
        pass

    @abstractmethod
    def list_tasks(
        self,
        context_id: str | None = None,
        state: TaskState | None = None,
        limit: int = 20,
    ) -> list[Task]:
        """List tasks by context or state."""
        pass
