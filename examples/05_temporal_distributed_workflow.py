#!/usr/bin/env python3
"""
Example 05: Durable Distributed A2A Workflows via Temporal.

Demonstrates executing a fault-tolerant, resumable A2A task across a Temporal
orchestration cluster using `TemporalTaskRunner`.
"""

import asyncio
import os
import uuid
from temporalio.client import Client

from a2a.models.message import Message
from a2a.models.task import TaskState
from a2a.runners.temporal.client import TemporalTaskRunner


async def main() -> None:
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    print(f"[*] Connecting to Temporal Cluster at {temporal_host} (override with TEMPORAL_HOST env var)...")

    try:
        temporal_client = await Client.connect(temporal_host, namespace="default")
        print("[+] Connected to Temporal namespace 'default'.")
    except Exception as exc:
        print(f"[-] Could not connect to Temporal at {temporal_host}: {exc}")
        print("    Ensure Temporal server is running (e.g., `temporal server start-dev` or remote cluster like 192.168.1.250:7233).")
        return

    runner = TemporalTaskRunner(
        client=temporal_client,
        task_queue="a2a-task-queue",
    )

    context_id = f"ctx-temporal-{uuid.uuid4().hex[:6]}"
    task_id = f"task-wf-{uuid.uuid4().hex[:6]}"
    initial_message = Message.from_text(
        text="Review quarterly financial audit anomalies and alert the audit team.",
        role="user",
        context_id=context_id,
    )

    print(f"[*] Dispatching durable workflow task '{task_id}' (queue: a2a-task-queue)...")

    # The Temporal worker running in the cluster executes activities and completes the workflow
    async def dummy_handler(task, msg):
        pass  # In Temporal execution, worker activities handle the computation

    completed_task, response_msg = await runner.execute_immediate(
        context_id=context_id,
        message=initial_message,
        handler=dummy_handler,
        task_id=task_id,
    )

    print(f"[+] Temporal Workflow Finished!")
    print(f"    Task ID: {completed_task.id}")
    print(f"    State:   {completed_task.status.state}")
    print(f"    Output:  {response_msg.get_text()}")
    print(f"    Artifacts generated: {len(completed_task.artifacts)}")
    for art in completed_task.artifacts:
        print(f"      - Artifact {art.id}: type={art.artifact_type}, data={art.data}")


if __name__ == "__main__":
    asyncio.run(main())
