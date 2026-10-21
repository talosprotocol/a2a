from __future__ import annotations

import pytest
from a2a.models import Artifact, Message, TaskState
from a2a.store import InMemoryTaskStore, SqliteTaskStore


@pytest.mark.parametrize("store_cls", [InMemoryTaskStore, lambda: SqliteTaskStore(":memory:")])
def test_task_stores_parity(store_cls):
    store = store_cls()

    # 1. Create Task
    msg = Message.from_text("Initial query", role="user", context_id="ctx-test")
    task = store.create_task("t-1", context_id="ctx-test", initial_message=msg, metadata={"env": "test"})
    assert task.id == "t-1"
    assert task.status.state == TaskState.SUBMITTED
    assert len(task.history) == 1

    # 2. Update Status
    st = store.update_status("t-1", TaskState.WORKING, message="Working...")
    assert st.state == TaskState.WORKING

    # 3. Append Message
    agent_msg = Message.from_text("Done", role="agent", context_id="ctx-test")
    store.append_message("t-1", agent_msg)

    # 4. Add Artifact
    art = Artifact("art-1", "Match", "text/plain", "data")
    store.add_artifact("t-1", art)

    # 5. Get Task
    fetched = store.get_task("t-1")
    assert fetched is not None
    assert fetched.status.state == TaskState.WORKING
    assert len(fetched.history) == 2
    assert len(fetched.artifacts) == 1
    assert fetched.artifacts[0].artifact_id == "art-1"

    # 6. List Tasks
    tasks = store.list_tasks(context_id="ctx-test")
    assert len(tasks) == 1
    assert tasks[0].id == "t-1"
