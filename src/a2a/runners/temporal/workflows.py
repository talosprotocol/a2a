from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from .activities import execute_a2a_step
from .contracts import ActivityStepInput, WorkflowTaskInput

LOGGER = logging.getLogger(__name__)

try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy
except ImportError:
    # Graceful fallback decorator if temporalio optional dependency is absent
    def workflow_defn(cls=None, **kwargs):
        if cls is not None:
            return cls
        return lambda c: c

    def _noop_decorator(fn=None, **kwargs):
        if fn is not None:
            return fn
        return lambda f: f

    class _WorkflowModule:
        defn = staticmethod(workflow_defn)
        run = staticmethod(_noop_decorator)
        query = staticmethod(_noop_decorator)
        signal = staticmethod(_noop_decorator)
        update = staticmethod(_noop_decorator)

        @staticmethod
        async def execute_activity(*args, **kwargs):
            raise NotImplementedError("temporalio not installed")

    workflow = _WorkflowModule()  # type: ignore

    class RetryPolicy:  # type: ignore
        def __init__(self, **kwargs):
            pass


@workflow.defn
class A2ATaskWorkflow:
    def __init__(self) -> None:
        self.state: str = "TASK_STATE_SUBMITTED"
        self.status_message: str = "Task initialized"
        self.events: list[dict[str, Any]] = []
        self.artifacts: list[dict[str, Any]] = []
        self.canceled: bool = False
        self.output_text: str = ""

    @workflow.run
    async def run(self, task_input: WorkflowTaskInput) -> dict[str, Any]:
        self.state = "TASK_STATE_WORKING"
        self.status_message = "Task workflow running"
        self.events.append({"state": self.state, "message": self.status_message})

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        try:
            # 1. Processing Step
            step_res = await workflow.execute_activity(
                execute_a2a_step,
                ActivityStepInput(
                    task_id=task_input.task_id,
                    context_id=task_input.context_id,
                    step_name="execute",
                    payload=task_input.metadata,
                ),
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=retry_policy,
            )

            if self.canceled:
                self.state = "TASK_STATE_CANCELED"
                self.status_message = "Task canceled"
                return {"state": self.state, "output": "Task was canceled", "artifacts": []}

            self.output_text = step_res.output_text
            self.artifacts = step_res.artifacts
            self.state = "TASK_STATE_COMPLETED"
            self.status_message = "Task completed successfully"
            self.events.append({"state": self.state, "message": self.status_message})

            return {
                "state": self.state,
                "output": self.output_text,
                "artifacts": self.artifacts,
            }

        except Exception as exc:
            self.state = "TASK_STATE_FAILED"
            self.status_message = str(exc)
            self.events.append({"state": self.state, "message": str(exc)})
            raise

    @workflow.query
    def get_task_state(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "status_message": self.status_message,
            "output_text": self.output_text,
            "artifacts": self.artifacts,
            "events": self.events,
            "canceled": self.canceled,
        }

    @workflow.signal
    def cancel_task(self, reason: str = "Canceled by user") -> None:
        self.canceled = True
        self.status_message = reason

    @workflow.update
    def fetch_recent_events(self, from_index: int) -> list[dict[str, Any]]:
        return self.events[from_index:]
