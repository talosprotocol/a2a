from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator

from ...models.artifact import Artifact
from ...models.events import StreamResponse, TaskStatusUpdateEvent
from ...models.message import Message
from ...models.task import Task, TaskState, TaskStatus, now_utc_iso
from ...store.base import BaseTaskStore
from ...store.memory import InMemoryTaskStore
from ..base import BaseTaskRunner, TaskExecutionHandler
from .contracts import WorkflowTaskInput
from .workflows import A2ATaskWorkflow

LOGGER = logging.getLogger(__name__)


class TemporalTaskRunner(BaseTaskRunner):
    """
    Durable A2A Task Runner backed by Temporal (temporalio).
    """

    def __init__(
        self,
        client: Any,  # temporalio.client.Client
        task_queue: str = "a2a-task-queue",
        store: BaseTaskStore | None = None,
    ) -> None:
        self.client = client
        self.task_queue = task_queue
        self.store = store or InMemoryTaskStore()

    async def execute_immediate(
        self,
        context_id: str,
        message: Message,
        handler: TaskExecutionHandler,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> tuple[Task, Message]:
        task_id = task_id or str(uuid.uuid4())
        task = self.store.create_task(
            task_id=task_id,
            context_id=context_id,
            initial_message=message,
            metadata=metadata,
        )

        wf_input = WorkflowTaskInput(
            task_id=task_id,
            context_id=context_id,
            message=message.to_dict(),
            metadata=metadata or {},
        )

        self.store.update_status(task_id, TaskState.WORKING, message="Temporal workflow dispatched")

        # Execute workflow synchronously to completion
        wf_result = await self.client.execute_workflow(
            A2ATaskWorkflow.run,
            wf_input,
            id=task_id,
            task_queue=self.task_queue,
        )

        final_state = TaskState.from_str(wf_result.get("state", "TASK_STATE_COMPLETED"))
        final_status = self.store.update_status(
            task_id,
            final_state,
            message="Temporal workflow finished",
        )

        output_text = wf_result.get("output", "")
        artifacts = [Artifact.from_dict(a) for a in wf_result.get("artifacts", [])]
        for art in artifacts:
            self.store.add_artifact(task_id, art)

        agent_msg = Message.from_text(output_text, role="agent", context_id=context_id)
        self.store.append_message(task_id, agent_msg)

        final_task = self.store.get_task(task_id) or task
        return final_task, agent_msg

    async def submit_task(
        self,
        context_id: str,
        message: Message,
        handler: TaskExecutionHandler,
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> Task:
        task_id = task_id or str(uuid.uuid4())
        task = self.store.create_task(
            task_id=task_id,
            context_id=context_id,
            initial_message=message,
            metadata=metadata,
        )

        wf_input = WorkflowTaskInput(
            task_id=task_id,
            context_id=context_id,
            message=message.to_dict(),
            metadata=metadata or {},
        )

        await self.client.start_workflow(
            A2ATaskWorkflow.run,
            wf_input,
            id=task_id,
            task_queue=self.task_queue,
        )

        self.store.update_status(task_id, TaskState.WORKING, message="Temporal workflow started")
        return task

    async def subscribe_task(self, task_id: str) -> AsyncGenerator[StreamResponse, None]:
        handle = self.client.get_workflow_handle(task_id)
        last_index = 0

        while True:
            try:
                state_query = await handle.query(A2ATaskWorkflow.get_task_state)
                events = state_query.get("events", [])
                for ev in events[last_index:]:
                    st = TaskStatus(
                        state=TaskState.from_str(ev.get("state", "TASK_STATE_WORKING")),
                        message=ev.get("message"),
                        timestamp=now_utc_iso(),
                    )
                    task = self.store.get_task(task_id)
                    context_id = task.context_id if task else "default"
                    yield StreamResponse(
                        status_update=TaskStatusUpdateEvent(
                            task_id=task_id,
                            context_id=context_id,
                            status=st,
                        )
                    )
                last_index = len(events)

                current_state = TaskState.from_str(state_query.get("state", "TASK_STATE_WORKING"))
                if current_state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}:
                    out_text = state_query.get("output_text", "")
                    yield StreamResponse(
                        message=Message.from_text(out_text, role="agent")
                    )
                    break

                await asyncio.sleep(1.0)
            except Exception as exc:
                LOGGER.debug("Temporal subscribe poll error for task %s: %s", task_id, exc)
                break

    async def wait_task(self, task_id: str, timeout: float = 180.0) -> Task | None:
        handle = self.client.get_workflow_handle(task_id)
        try:
            wf_result = await asyncio.wait_for(handle.result(), timeout=timeout)
            final_state = TaskState.from_str(wf_result.get("state", "TASK_STATE_COMPLETED"))
            self.store.update_status(task_id, final_state, message="Completed")
            return self.store.get_task(task_id)
        except asyncio.TimeoutError:
            return self.store.get_task(task_id)

    def cancel_task(self, task_id: str, reason: str = "Canceled by user") -> bool:
        handle = self.client.get_workflow_handle(task_id)
        try:
            # Send signal or cancel workflow
            asyncio.create_task(handle.signal(A2ATaskWorkflow.cancel_task, reason))
            self.store.update_status(task_id, TaskState.CANCELED, message=reason)
            return True
        except Exception as exc:
            LOGGER.warning("Failed to cancel Temporal task %s: %s", task_id, exc)
            return False

    def get_task(self, task_id: str) -> Task | None:
        return self.store.get_task(task_id)

    def list_tasks(
        self,
        context_id: str | None = None,
        state: TaskState | None = None,
        limit: int = 20,
    ) -> list[Task]:
        return self.store.list_tasks(context_id=context_id, state=state, limit=limit)
