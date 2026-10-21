from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from .activities import (
    execute_a2a_step,
    notify_telegram_digest_activity,
    search_startups_activity,
    sync_lounge_messages_activity,
    synthesize_outreach_activity,
)
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


@workflow.defn
class A2AOutreachWorkflow:
    """
    Durable multi-step agent workflow that searches startups in Qdrant and synthesizes
    tailored Talos Protocol partner outreach campaigns using local DeepSeek-R1.
    """
    def __init__(self) -> None:
        self.state: str = "TASK_STATE_SUBMITTED"
        self.status_message: str = "Campaign workflow initialized"
        self.startups: list[dict[str, Any]] = []
        self.campaign_output: str = ""
        self.canceled: bool = False

    @workflow.run
    async def run(self, target_focus: str, limit: int = 3) -> dict[str, Any]:
        self.state = "TASK_STATE_WORKING"
        self.status_message = f"Searching Qdrant startups for focus '{target_focus}'..."

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        # 1. Search Startups Activity
        self.startups = await workflow.execute_activity(
            search_startups_activity,
            args=[target_focus, limit],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        if self.canceled:
            self.state = "TASK_STATE_CANCELED"
            return {"state": self.state, "output": "Workflow canceled", "startups": []}

        self.status_message = f"Synthesizing DeepSeek-R1 outreach for {len(self.startups)} startups..."

        # 2. Synthesis Activity
        self.campaign_output = await workflow.execute_activity(
            synthesize_outreach_activity,
            args=[self.startups, target_focus],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        self.state = "TASK_STATE_COMPLETED"
        self.status_message = "Outreach campaign generated successfully"

        return {
            "state": self.state,
            "output": self.campaign_output,
            "startups": self.startups,
            "target_focus": target_focus,
        }

    @workflow.query
    def get_campaign_state(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "status_message": self.status_message,
            "startups": self.startups,
            "output": self.campaign_output,
            "canceled": self.canceled,
        }

    @workflow.signal
    def cancel(self, reason: str = "Canceled by user") -> None:
        self.canceled = True
        self.status_message = reason


@workflow.defn
class LoungeSyncWorkflow:
    """
    Recurring or on-demand workflow that syncs WhatsApp AI Founders Lounge messages,
    verifies startup profiles in Qdrant, and sends a digest to Telegram.
    """
    def __init__(self) -> None:
        self.state: str = "TASK_STATE_SUBMITTED"
        self.sync_result: dict[str, Any] = {}

    @workflow.run
    async def run(self, openwa_url: str = "http://192.168.1.229:8081", notify_telegram: bool = True) -> dict[str, Any]:
        self.state = "TASK_STATE_WORKING"
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=5),
            maximum_attempts=2,
        )

        # 1. Sync messages and verify index
        self.sync_result = await workflow.execute_activity(
            sync_lounge_messages_activity,
            args=[openwa_url, 50],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        # 2. Optional Telegram notification
        if notify_telegram:
            pts = self.sync_result.get("points_count", 0)
            digest = (
                f"🔄 *Talos Lounge Periodic Sync Completed*\n\n"
                f"• **Index Status:** `{pts}` startups indexed in Qdrant vector database\n"
                f"• **Target Queue:** `a2a-task-queue` (Fedora Worker Fleet)\n"
                f"• **Status:** Operational"
            )
            await workflow.execute_activity(
                notify_telegram_digest_activity,
                args=[digest],
                start_to_close_timeout=timedelta(seconds=15),
            )

        self.state = "TASK_STATE_COMPLETED"
        return {
            "state": self.state,
            "sync_result": self.sync_result,
        }

