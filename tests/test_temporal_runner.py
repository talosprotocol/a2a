from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from a2a import Message, TaskState, TemporalTaskRunner
from a2a.runners.temporal.activities import execute_a2a_step
from a2a.runners.temporal.contracts import ActivityStepInput, WorkflowTaskInput
from a2a.runners.temporal.workflows import A2ATaskWorkflow


@pytest.mark.asyncio
async def test_temporal_activity():
    inp = ActivityStepInput(
        task_id="t-act",
        context_id="c-act",
        step_name="analyze",
        payload={"param": 1},
    )
    res = await execute_a2a_step(inp)
    assert "Completed analyze" in res.output_text
    assert res.status_message == "Activity analyze executed"


def test_temporal_workflow_signals_and_queries():
    wf = A2ATaskWorkflow()
    assert wf.state == "TASK_STATE_SUBMITTED"

    state = wf.get_task_state()
    assert state["state"] == "TASK_STATE_SUBMITTED"
    assert state["canceled"] is False

    wf.cancel_task(reason="Abort execution")
    assert wf.canceled is True
    assert wf.status_message == "Abort execution"


@pytest.mark.asyncio
async def test_temporal_task_runner_with_mock_client():
    mock_client = MagicMock()
    mock_client.execute_workflow = AsyncMock(
        return_value={
            "state": "TASK_STATE_COMPLETED",
            "output": "Temporal output result",
            "artifacts": [{"artifactId": "art-wf", "name": "Report", "mimeType": "text/plain", "data": "ok"}],
        }
    )
    mock_client.start_workflow = AsyncMock()

    runner = TemporalTaskRunner(client=mock_client, task_queue="test-queue")

    # 1. Immediate Execution
    msg = Message.from_text("Run durable task", role="user", context_id="ctx-wf")
    task, agent_msg = await runner.execute_immediate(
        context_id="ctx-wf",
        message=msg,
        handler=AsyncMock(),
    )

    assert task.status.state == TaskState.COMPLETED
    assert agent_msg.get_text() == "Temporal output result"
    assert len(task.artifacts) == 1
    assert task.artifacts[0].name == "Report"
    assert mock_client.execute_workflow.called

    # 2. Async Submit
    submit_task = await runner.submit_task(
        context_id="ctx-wf",
        message=msg,
        handler=AsyncMock(),
    )
    assert submit_task.status.state == TaskState.WORKING
    assert mock_client.start_workflow.called
