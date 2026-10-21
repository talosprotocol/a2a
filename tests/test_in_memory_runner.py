from __future__ import annotations

import asyncio
import pytest
from a2a import Artifact, InMemoryTaskRunner, Message, TaskState


@pytest.mark.asyncio
async def test_in_memory_runner_immediate():
    runner = InMemoryTaskRunner()

    async def mock_handler(task, emit_status, is_cancelled):
        await emit_status("Step 1 done")
        art = Artifact(artifact_id="art-1", name="Res", mime_type="text/plain", data="result")
        return "Task complete", [art]

    msg = Message.from_text("Run immediate", role="user", context_id="ctx-imm")
    task, agent_msg = await runner.execute_immediate(
        context_id="ctx-imm",
        message=msg,
        handler=mock_handler,
    )

    assert task.status.state == TaskState.COMPLETED
    assert agent_msg.get_text() == "Task complete"
    assert len(task.artifacts) == 1
    assert task.artifacts[0].name == "Res"


@pytest.mark.asyncio
async def test_in_memory_runner_streaming_and_wait():
    runner = InMemoryTaskRunner()

    async def mock_handler(task, emit_status, is_cancelled):
        await emit_status("Working 1...")
        await asyncio.sleep(0.02)
        await emit_status("Working 2...")
        return "Stream done", []

    msg = Message.from_text("Run stream", role="user", context_id="ctx-str")
    task = await runner.submit_task(
        context_id="ctx-str",
        message=msg,
        handler=mock_handler,
    )

    events = []
    async for chunk in runner.subscribe_task(task.id):
        events.append(chunk)

    assert any(e.status_update and "Working 1" in (e.status_update.status.message or "") for e in events)
    assert any(e.status_update and "Working 2" in (e.status_update.status.message or "") for e in events)
    assert any(e.message and e.message.get_text() == "Stream done" for e in events)

    waited_task = await runner.wait_task(task.id, timeout=1.0)
    assert waited_task is not None
    assert waited_task.status.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_in_memory_runner_cancellation():
    runner = InMemoryTaskRunner()

    async def infinite_handler(task, emit_status, is_cancelled):
        await emit_status("Running...")
        while not is_cancelled():
            await asyncio.sleep(0.01)
        return "Aborted", []

    msg = Message.from_text("Infinite", role="user", context_id="ctx-cancel")
    task = await runner.submit_task(context_id="ctx-cancel", message=msg, handler=infinite_handler)

    await asyncio.sleep(0.02)
    canceled = runner.cancel_task(task.id, reason="User stop")
    assert canceled is True

    term_task = runner.get_task(task.id)
    assert term_task is not None
    assert term_task.status.state == TaskState.CANCELED
