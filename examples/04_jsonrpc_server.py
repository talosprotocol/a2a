"""
Example 04: JSON-RPC 2.0 Dispatcher & A2A Task Engine
Demonstrates using the standard A2AJsonRpcDispatcher to parse and execute canonical
JSON-RPC 2.0 requests (tasks/send, tasks/get, tasks/cancel).
"""

import asyncio
import json
from a2a import A2AJsonRpcDispatcher, InMemoryTaskRunner, InMemoryTaskStore, Task, TaskState


async def sample_handler(task: Task, emit_status, is_cancelled) -> tuple[str, list]:
    await emit_status("Processing RPC task request...")
    return f"Computed result for context: {task.context_id}", []


async def main():
    store = InMemoryTaskStore()
    runner = InMemoryTaskRunner(store=store)
    dispatcher = A2AJsonRpcDispatcher(runner=runner, default_handler=sample_handler)

    print("--- 1. Send Task via JSON-RPC 2.0 ---")
    send_payload = {
        "jsonrpc": "2.0",
        "id": "req-001",
        "method": "tasks/send",
        "params": {
            "contextId": "rpc-ctx-99",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Execute zero-trust agent verification"}],
            },
            "returnImmediately": False,
        },
    }

    resp = await dispatcher.dispatch(send_payload)
    print("Response:")
    print(json.dumps(resp, indent=2))
    task_id = resp["result"]["task"]["id"]

    print("\n--- 2. Get Task State via JSON-RPC 2.0 ---")
    get_payload = {
        "jsonrpc": "2.0",
        "id": "req-002",
        "method": "tasks/get",
        "params": {"taskId": task_id},
    }
    resp = await dispatcher.dispatch(get_payload)
    print(f"Task state: {resp['result']['task']['status']['state']}")

    print("\n--- 3. Invalid Method Error Handling ---")
    bad_payload = {
        "jsonrpc": "2.0",
        "id": "req-003",
        "method": "unknown/operation",
        "params": {},
    }
    resp = await dispatcher.dispatch(bad_payload)
    print("Error response:", json.dumps(resp))


if __name__ == "__main__":
    asyncio.run(main())
