"""
Example 02: Real-Time Streaming Task Updates
Demonstrates subscribing to an A2A task event stream, receiving incremental status
and artifact events as the agent works, and formatting them as Server-Sent Events (SSE).
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
from a2a.rpc.sse import format_sse_event


async def streaming_agent_handler(task: Task, emit_status, is_cancelled) -> tuple[str, list[Artifact]]:
    """Simulates a multi-stage reasoning agent."""
    await emit_status("Stage 1/3: Analyzing repository structure...")
    await asyncio.sleep(0.05)

    await emit_status("Stage 2/3: Identifying zero-trust cryptographic requirements...")
    await asyncio.sleep(0.05)

    await emit_status("Stage 3/3: Generating integration blueprint...")
    await asyncio.sleep(0.05)

    blueprint_artifact = Artifact(
        artifact_id="talos-blueprint-001",
        name="A2A Integration Blueprint",
        mime_type="text/markdown",
        data="# Talos A2A Integration Blueprint\n- Use W3C DIDs for agent identity\n- Enable Double Ratchet E2EE",
    )
    return "Analysis completed successfully. Blueprint generated.", [blueprint_artifact]


async def main():
    store = InMemoryTaskStore()
    runner = InMemoryTaskRunner(store=store)

    msg = Message(
        role="user",
        parts=[TextPart(text="Design zero-trust A2A security architecture")],
    )

    print("--- Submitting Task and Subscribing to Stream ---")
    task = await runner.submit_task(
        context_id="stream-ctx-001",
        message=msg,
        handler=streaming_agent_handler,
    )

    async for stream_resp in runner.subscribe_task(task.id):
        if stream_resp.status_update:
            status = stream_resp.status_update.status
            print(f"[STATUS] State: {status.state.value:<10} | Message: {status.message}")
        elif stream_resp.artifact_update:
            art = stream_resp.artifact_update.artifact
            print(f"[ARTIFACT] Emitted: '{art.name}' ({art.mime_type})")

        # Format as standard Server-Sent Event (SSE)
        sse_chunk = format_sse_event(stream_resp)
        # print("SSE Line:", repr(sse_chunk))

    # Retrieve terminal task state from store
    task = store.get_task(stream_resp.status_update.task_id if stream_resp.status_update else "")
    if task:
        print(f"\nFinal Terminal Task State: {task.status.state}")


if __name__ == "__main__":
    asyncio.run(main())
