"""Tests for the sync-to-async upgrade behaviour in the A2A JSON-RPC dispatcher.

Protocol contract
-----------------
* tasks/send without ``returnImmediately`` attempts to resolve synchronously within
  *syncTimeoutSeconds* (default 10 s, overrideable per request via ``configuration``).
* If it resolves inside the window  → synchronous response with task + message.
* If not                            → async/polling response with async=True + hints.
* Hard ceiling (executionTimeoutSeconds, default 180 s) kills the background task and
  marks it FAILED with error_code=TASK_EXECUTION_TIMEOUT.
* ``returnImmediately=true`` bypasses the sync window entirely (unchanged behaviour).
* tasks/get always returns the current snapshot so clients can poll.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

import pytest

from a2a.models.artifact import Artifact
from a2a.models.message import Message
from a2a.models.task import Task, TaskState
from a2a.runners.in_memory import InMemoryTaskRunner
from a2a.rpc.jsonrpc import A2AJsonRpcDispatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TaskHandler = Callable[
    [Task, Callable[[str, dict[str, Any] | None], Awaitable[None]], Callable[[], bool]],
    Awaitable[tuple[str, list[Artifact]]],
]


def _make_send_payload(
    text: str = "hello",
    context_id: str = "ctx-test",
    return_immediately: bool = False,
    sync_timeout: float | None = None,
    execution_timeout: float | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if return_immediately:
        config["returnImmediately"] = True
    if sync_timeout is not None:
        config["syncTimeoutSeconds"] = sync_timeout
    if execution_timeout is not None:
        config["executionTimeoutSeconds"] = execution_timeout

    return {
        "jsonrpc": "2.0",
        "id": "r1",
        "method": "tasks/send",
        "params": {
            "message": {
                "role": "user",
                "contextId": context_id,
                "parts": [{"text": text}],
            },
            "configuration": config,
        },
    }


def _fast_handler(delay: float = 0.0) -> TaskHandler:
    """Returns a handler that completes after *delay* seconds."""

    async def handler(
        task: Task,
        emit_status: Callable[[str, dict[str, Any] | None], Awaitable[None]],
        check_cancelled: Callable[[], bool],
    ) -> tuple[str, list[Artifact]]:
        if delay:
            await asyncio.sleep(delay)
        return "done", []

    return handler


def _make_dispatcher(
    handler: TaskHandler,
    sync_timeout: float = 10.0,
    execution_timeout: float = 180.0,
) -> A2AJsonRpcDispatcher:
    runner = InMemoryTaskRunner()
    return A2AJsonRpcDispatcher(
        runner=runner,
        default_handler=handler,
        sync_timeout=sync_timeout,
        execution_timeout=execution_timeout,
    )


# ---------------------------------------------------------------------------
# Test 1: Fast task resolves synchronously
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fast_task_returns_synchronously() -> None:
    """A handler that completes instantly should give a sync response (task + message)."""
    dispatcher = _make_dispatcher(_fast_handler(delay=0.0), sync_timeout=0.5)
    payload = _make_send_payload()

    resp = await dispatcher.dispatch(payload)

    assert resp["jsonrpc"] == "2.0"
    result = resp["result"]
    assert "task" in result
    assert "message" in result
    assert result.get("async") is None, "async flag must NOT be set for sync completions"
    assert result["task"]["status"]["state"] == TaskState.COMPLETED.value


# ---------------------------------------------------------------------------
# Test 2: Slow task upgrades to async response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slow_task_upgrades_to_async() -> None:
    """A handler that takes longer than syncTimeoutSeconds should return async hints."""
    # sync window = 50 ms; handler takes 300 ms → must overflow
    dispatcher = _make_dispatcher(_fast_handler(delay=0.3), sync_timeout=0.05)
    payload = _make_send_payload()

    resp = await dispatcher.dispatch(payload)

    result = resp["result"]
    assert result.get("async") is True, "async flag must be True when sync window expires"
    assert "pollIntervalMs" in result
    assert "executionTimeoutSeconds" in result
    assert "expiresAt" in result
    # Task state must still be a non-terminal working state
    task_state = result["task"]["status"]["state"]
    assert task_state in {TaskState.SUBMITTED.value, TaskState.WORKING.value}

    # Give the background task time to complete so the event loop doesn't complain
    await asyncio.sleep(0.5)


# ---------------------------------------------------------------------------
# Test 3: Execution ceiling kills long-running tasks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execution_timeout_marks_task_failed() -> None:
    """A handler that never finishes must be killed and marked FAILED."""
    # execution ceiling = 200 ms; handler sleeps forever
    async def never_finishes(
        task: Task,
        emit_status: Any,
        check_cancelled: Any,
    ) -> tuple[str, list[Artifact]]:
        await asyncio.sleep(9999)
        return "never", []

    runner = InMemoryTaskRunner()
    dispatcher = A2AJsonRpcDispatcher(
        runner=runner,
        default_handler=never_finishes,
        sync_timeout=0.05,          # overflow immediately
        execution_timeout=0.2,      # kill after 200 ms
    )

    payload = _make_send_payload()
    resp = await dispatcher.dispatch(payload)

    # We get an async response first (sync window expired)
    assert resp["result"].get("async") is True
    task_id = resp["result"]["task"]["id"]

    # Wait long enough for the ceiling to fire
    await asyncio.sleep(0.5)

    # Poll via tasks/get
    get_resp = await dispatcher.dispatch({
        "jsonrpc": "2.0",
        "id": "g1",
        "method": "tasks/get",
        "params": {"taskId": task_id},
    })
    task_data = get_resp["result"]["task"]
    assert task_data["status"]["state"] == TaskState.FAILED.value
    details = task_data["status"].get("details") or {}
    assert details.get("error_code") == "TASK_EXECUTION_TIMEOUT"


# ---------------------------------------------------------------------------
# Test 4: returnImmediately bypasses sync window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_immediately_bypasses_sync_window() -> None:
    """returnImmediately=true must return a SUBMITTED/WORKING task without waiting."""
    dispatcher = _make_dispatcher(_fast_handler(delay=0.0), sync_timeout=0.05)
    payload = _make_send_payload(return_immediately=True)

    resp = await dispatcher.dispatch(payload)

    result = resp["result"]
    assert "task" in result
    assert result.get("async") is None, "returnImmediately must not add async flag"
    # message key is NOT expected in returnImmediately response
    assert "message" not in result or result["message"] is None
    # Task state is initial (not yet completed at response time)
    task_state = result["task"]["status"]["state"]
    assert task_state in {TaskState.SUBMITTED.value, TaskState.WORKING.value}

    # Allow the handler to complete
    await asyncio.sleep(0.1)


# ---------------------------------------------------------------------------
# Test 5: Client polls tasks/get after async upgrade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_polls_tasks_get_after_async_upgrade() -> None:
    """After receiving async=True, the client polls tasks/get and eventually
    sees COMPLETED with the result message in the task history."""
    # sync window = 50 ms; handler finishes after 300 ms
    dispatcher = _make_dispatcher(_fast_handler(delay=0.3), sync_timeout=0.05)
    payload = _make_send_payload()

    resp = await dispatcher.dispatch(payload)
    assert resp["result"].get("async") is True
    task_id = resp["result"]["task"]["id"]

    # Poll until terminal state or give up after 10 iterations
    final_state = None
    for _ in range(10):
        await asyncio.sleep(0.1)
        get_resp = await dispatcher.dispatch({
            "jsonrpc": "2.0",
            "id": "poll",
            "method": "tasks/get",
            "params": {"taskId": task_id},
        })
        state = get_resp["result"]["task"]["status"]["state"]
        if state == TaskState.COMPLETED.value:
            final_state = state
            break

    assert final_state == TaskState.COMPLETED.value, (
        f"Expected COMPLETED after polling but got: {final_state}"
    )
    # The agent's reply should be in the task history
    history = get_resp["result"]["task"]["history"]
    assert any(
        any(p.get("text") == "done" for p in (m.get("parts") or []))
        for m in history
        if m.get("role") == "agent"
    ), "Agent message 'done' should appear in task history"
