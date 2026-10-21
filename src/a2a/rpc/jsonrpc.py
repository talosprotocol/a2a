from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable

from ..models.message import Message
from ..models.task import TaskState
from ..runners.base import BaseTaskRunner, TaskExecutionHandler

LOGGER = logging.getLogger(__name__)

ALLOWED_A2A_METHODS = {
    "SendMessage",
    "SendStreamingMessage",
    "GetTask",
    "SubscribeToTask",
    "CancelTask",
    "ListTasks",
    "GetExtendedAgentCard",
    "agent/getAuthenticatedExtendedCard",
    "agent/card",
    "agent.card",
    "tasks/send",
    "tasks.send",
    "tasks/get",
    "tasks.get",
    "tasks/cancel",
    "tasks.cancel",
    "tasks/list",
    "tasks.list",
}


class A2AJsonRpcDispatcher:
    # Default sync window: block up to this many seconds waiting for completion.
    # If the task hasn't finished by then, return an async/polling response.
    DEFAULT_SYNC_TIMEOUT: float = 10.0

    # Default hard ceiling: background task is killed and marked FAILED if it
    # hasn't completed within this many seconds.
    DEFAULT_EXECUTION_TIMEOUT: float = 180.0

    def __init__(
        self,
        runner: BaseTaskRunner,
        default_handler: TaskExecutionHandler,
        agent_card_provider: Callable[[], dict[str, Any]] | None = None,
        sync_timeout: float | None = None,
        execution_timeout: float | None = None,
    ) -> None:
        self.runner = runner
        self.default_handler = default_handler
        self.agent_card_provider = agent_card_provider or (
            lambda: {
                "name": "A2A Agent",
                "version": "1.0.0",
                "protocol": "a2a-v1",
                "supportedTaskModes": ["immediate", "streaming", "wait", "get"],
            }
        )
        # Allow per-instance override; fall back to class-level defaults.
        self._sync_timeout = sync_timeout if sync_timeout is not None else self.DEFAULT_SYNC_TIMEOUT
        self._exec_timeout = (
            execution_timeout if execution_timeout is not None else self.DEFAULT_EXECUTION_TIMEOUT
        )

    async def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        req_id = payload.get("id")

        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": {"details": "jsonrpc must be '2.0'"},
                },
            }

        method = payload.get("method")
        if not isinstance(method, str) or method not in ALLOWED_A2A_METHODS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"method": method},
                },
            }

        params = payload.get("params") or {}
        if not isinstance(params, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"details": "params must be object"},
                },
            }

        try:
            if method in {"GetExtendedAgentCard", "agent/getAuthenticatedExtendedCard", "agent/card", "agent.card"}:
                card = self.agent_card_provider()
                if hasattr(card, "to_dict"):
                    card = card.to_dict()
                return {"jsonrpc": "2.0", "id": req_id, "result": card}

            elif method in {"SendMessage", "tasks/send", "tasks.send"}:
                msg_data = params.get("message")
                if not msg_data or not isinstance(msg_data, dict):
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": {"details": "message object required"},
                        },
                    }
                message = Message.from_dict(msg_data)
                config = params.get("configuration") or {}
                return_immediately = bool(config.get("returnImmediately", False))
                context_id = message.context_id or "default"

                # Per-request overrides take precedence; fall back to dispatcher defaults.
                sync_timeout: float = float(
                    config.get("syncTimeoutSeconds", self._sync_timeout)
                )
                exec_timeout: float = float(
                    config.get("executionTimeoutSeconds", self._exec_timeout)
                )

                # Always submit to the background runner so we have a task record.
                task = await self.runner.submit_task(
                    context_id=context_id,
                    message=message,
                    handler=self.default_handler,
                    metadata=params.get("metadata"),
                    execution_timeout=exec_timeout,
                )

                # returnImmediately=true: skip the sync window entirely.
                if return_immediately:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"task": task.to_dict()},
                    }

                # Attempt to resolve within the sync window.
                try:
                    completed = await asyncio.wait_for(
                        self.runner.wait_task(task.id, timeout=exec_timeout),
                        timeout=sync_timeout,
                    )
                    if completed is None:
                        completed = task
                    latest_msg = completed.latest_message
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "task": completed.to_dict(),
                            "message": latest_msg.to_dict() if latest_msg else None,
                        },
                    }
                except asyncio.TimeoutError:
                    # Sync window expired — task is still running in the background.
                    expires_at = (
                        datetime.datetime.now(datetime.timezone.utc)
                        + datetime.timedelta(seconds=exec_timeout)
                    ).isoformat()
                    working_task = self.runner.get_task(task.id) or task
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "task": working_task.to_dict(),
                            "async": True,
                            "pollIntervalMs": 1000,
                            "executionTimeoutSeconds": exec_timeout,
                            "expiresAt": expires_at,
                        },
                    }

            elif method in {"GetTask", "tasks/get", "tasks.get"}:
                task_id = params.get("taskId") or params.get("id")
                if not task_id:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": {"details": "taskId or id required"},
                        },
                    }
                task = self.runner.get_task(str(task_id))
                if not task:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32004,
                            "message": "Task not found",
                            "data": {"taskId": task_id},
                        },
                    }
                return {"jsonrpc": "2.0", "id": req_id, "result": {"task": task.to_dict()}}

            elif method in {"CancelTask", "tasks/cancel", "tasks.cancel"}:
                task_id = params.get("taskId") or params.get("id")
                reason = params.get("reason", "Canceled via A2A CancelTask")
                if not task_id:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": {"details": "taskId required"},
                        },
                    }
                ok = self.runner.cancel_task(str(task_id), reason=reason)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"taskId": task_id, "canceled": ok},
                }

            elif method in {"ListTasks", "tasks/list", "tasks.list"}:
                context_id = params.get("contextId")
                state_str = params.get("state")
                state = TaskState.from_str(state_str) if state_str else None
                limit = int(params.get("limit", 20))
                tasks = self.runner.list_tasks(context_id=context_id, state=state, limit=limit)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tasks": [t.to_dict() for t in tasks]},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Method not implemented in dispatcher",
                    "data": {"method": method},
                },
            }

        except Exception as exc:
            LOGGER.exception("A2A dispatcher error for method %s: %s", method, exc)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"details": str(exc)},
                },
            }
