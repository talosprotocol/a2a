"""
Example 01: In-Memory Task Execution (Immediate & Non-Blocking)
Demonstrates setting up an in-memory task runner, creating a task message,
registering an agent execution handler, and retrieving completed results and artifacts.
"""

import asyncio
from a2a import (
    Artifact,
    InMemoryTaskRunner,
    InMemoryTaskStore,
    Message,
    Task,
    TaskState,
    TextPart,
)


async def sample_agent_handler(task: Task, emit_status, is_cancelled) -> tuple[str, list[Artifact]]:
    """Simulates an autonomous agent performing analysis."""
    # 1. Cooperative cancellation check
    if is_cancelled():
        return "Task was canceled", []

    # 2. Emit intermediate progress event
    await emit_status("Performing security perimeter analysis...")

    # 3. Produce output text and attach an artifact
    output = "Perimeter scan complete. 0 vulnerabilities found."
    artifact = Artifact(
        artifact_id="perimeter-scan-report",
        name="Security Audit Report",
        mime_type="application/json",
        data='{"perimeter": "secure", "threat_level": "LOW"}',
    )
    return output, [artifact]


async def main():
    store = InMemoryTaskStore()
    runner = InMemoryTaskRunner(store=store)

    # Construct an A2A Message
    msg = Message(
        role="user",
        parts=[TextPart(text="Scan security perimeter of cluster node 1")],
    )

    print("--- 1. Immediate (Blocking) Execution ---")
    task, agent_response = await runner.execute_immediate(
        context_id="session-001",
        message=msg,
        handler=sample_agent_handler,
    )

    print(f"Task ID: {task.id}")
    print(f"Final State: {task.status.state}")
    print(f"Agent Response: {agent_response.get_text()}")
    print(f"Artifacts: {[a.name for a in task.artifacts]}\n")

    print("--- 2. Non-Blocking (Submit & Wait) Execution ---")
    submitted_task = await runner.submit_task(
        context_id="session-001",
        message=msg,
        handler=sample_agent_handler,
    )
    print(f"Submitted Task ID: {submitted_task.id} (State: {submitted_task.status.state})")

    # Await completion barrier
    completed_task = await runner.wait_task(submitted_task.id, timeout=5.0)
    print(f"Task After Wait: {completed_task.id} (State: {completed_task.status.state})")


if __name__ == "__main__":
    asyncio.run(main())
