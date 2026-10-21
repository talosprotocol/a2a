from __future__ import annotations

import pytest
from a2a import A2AJsonRpcDispatcher, InMemoryTaskRunner, Message, TaskState


@pytest.mark.asyncio
async def test_jsonrpc_dispatcher_flows():
    runner = InMemoryTaskRunner()

    async def rpc_handler(task, emit_status, is_cancelled):
        return "RPC output", []

    dispatcher = A2AJsonRpcDispatcher(runner, default_handler=rpc_handler)

    # 1. GetExtendedAgentCard
    card_res = await dispatcher.dispatch({"jsonrpc": "2.0", "id": 1, "method": "GetExtendedAgentCard"})
    assert card_res["id"] == 1
    assert card_res["result"]["protocol"] == "a2a-v1"

    # 2. SendMessage (Immediate)
    send_imm = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Hello"}],
                "contextId": "rpc-ctx",
            },
            "configuration": {"returnImmediately": False},
        },
    }
    imm_res = await dispatcher.dispatch(send_imm)
    assert imm_res["id"] == 2
    assert imm_res["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    assert imm_res["result"]["message"]["parts"][0]["text"] == "RPC output"
    task_id = imm_res["result"]["task"]["id"]

    # 3. GetTask
    get_res = await dispatcher.dispatch({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "GetTask",
        "params": {"taskId": task_id},
    })
    assert get_res["result"]["task"]["id"] == task_id

    # 4. ListTasks
    list_res = await dispatcher.dispatch({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "ListTasks",
        "params": {"contextId": "rpc-ctx"},
    })
    assert len(list_res["result"]["tasks"]) >= 1

    # 5. CancelTask
    cancel_res = await dispatcher.dispatch({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "CancelTask",
        "params": {"taskId": task_id},
    })
    # Since task was already completed, canceled is False
    assert cancel_res["result"]["canceled"] is False

    # 6. Error handling - invalid method
    err_method = await dispatcher.dispatch({"jsonrpc": "2.0", "id": 6, "method": "NonExistent"})
    assert err_method["error"]["code"] == -32601

    # 7. Error handling - invalid jsonrpc version
    err_ver = await dispatcher.dispatch({"jsonrpc": "1.0", "id": 7, "method": "GetTask"})
    assert err_ver["error"]["code"] == -32600
