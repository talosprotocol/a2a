# talosprotocol/a2a

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Status: Production Ready](https://img.shields.io/badge/status-production--ready-success.svg)]()

Universal, protocol-pure **Agent-to-Agent (A2A)** runtime engine and communication standard. Supports pluggable execution drivers (**In-Memory** & **Temporal Distributed**), blocking & streaming delivery modes, multimodal payloads (**Text**, **Voice Audio Streams**, **Video Keyframes**), and persistent storage (**Memory** & **SQLite**).

---

## Architecture Overview

```mermaid
flowchart TD
    Client[A2A Client / Calling Agent] -->|JSON-RPC 2.0 / SSE| Dispatcher[A2A Transport Dispatcher]
    Dispatcher --> RunnerSelect{Execution Runner}

    subgraph Runners
        RunnerSelect -->|Local / Edge / Testing| InMemory[InMemoryTaskRunner\n(Asyncio Queues)]
        RunnerSelect -->|Distributed / Resilient| Temporal[TemporalTaskRunner\n(Cluster Workflows)]
    end

    subgraph Stores
        InMemory --> StoreSelect{Task Store}
        Temporal --> StoreSelect
        StoreSelect --> MemStore[InMemoryTaskStore]
        StoreSelect --> SqliteStore[SQLiteTaskStore]
    end

    subgraph Multimodal Engine
        InMemory --- MultiCodec[Multimodal Codec\nTextPart · AudioPart · VideoPart]
        Temporal --- MultiCodec
    end
```

---

## Key Features

- **Protocol-Pure A2A v1 Compliance**: Full implementation of canonical task lifecycles, states (`SUBMITTED`, `WORKING`, `COMPLETED`, `FAILED`, `CANCELED`), message threads, and structured artifacts.
- **Dual Pluggable Execution Drivers**:
  - `InMemoryTaskRunner`: High-throughput, zero-dependency, local asyncio queues and pub/sub events for edge instances (Raspberry Pi, mobile, IoT) and fast unit testing.
  - `TemporalTaskRunner`: Durable, distributed workflow execution with cross-node task queues, saga compensation, and automatic retries.
- **Multiple Execution Modes**:
  - **Immediate (Blocking)**: Low-latency synchronous execution (`execute_immediate`).
  - **Submit (Non-Blocking)**: Asynchronous task dispatch returning a task handle (`submit_task`).
  - **Streaming**: Real-time async streaming of intermediate tokens, reasoning traces (`<think>`), audio chunks, and task state updates (`subscribe_task`).
- **First-Class Multimodal Payloads**:
  - `TextPart`: Natural language, prompt instructions, structured JSON/YAML.
  - `AudioPart`: Raw PCM / Opus audio chunks, sample rate negotiation, and streaming buffers (`AudioStreamBuffer`).
  - `VideoPart`: Keyframes, video segments, and spatial bounding-box annotations (`create_bounding_box_artifact`).
- **RPC & Streaming Transports**:
  - `A2AJsonRpcDispatcher`: Standard JSON-RPC 2.0 request parsing, method routing (`tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/list`), error code handling.
  - SSE Event Formatter: Ready for integration with FastAPI, Starlette, Quart, or Flask.

---

## Installation

### From Source
```bash
git clone https://github.com/talosprotocol/a2a.git
cd a2a

# Basic in-memory and multimodal engine
pip install -e .

# With Temporal distributed workflow support
pip install -e ".[temporal]"
```

---

## Copy-Paste Runnable Examples

All examples below are standalone, verified, and located in the `examples/` directory.

### 1. Immediate In-Memory Task Execution

Run a task synchronously and obtain the completed task and response message:

```python
import asyncio
from a2a.models.message import Message
from a2a.models.artifact import Artifact
from a2a.models.task import Task, TaskState
from a2a.runners.in_memory import InMemoryTaskRunner

async def weather_agent_handler(task: Task, incoming: Message) -> Message:
    # Perform agent computation
    user_query = incoming.get_text()
    
    # Attach a structured artifact to the task
    task.artifacts.append(
        Artifact.structured_data(
            name="forecast_data",
            data={"city": "San Francisco", "temp_c": 18.5, "condition": "Sunny"}
        )
    )
    return Message.from_text(
        text=f"Processed query '{user_query}'. Current temperature is 18.5°C with clear skies.",
        role="agent",
        context_id=incoming.context_id
    )

async def main():
    runner = InMemoryTaskRunner()
    user_msg = Message.from_text("What is the weather in San Francisco?", role="user", context_id="ctx-001")

    task, reply = await runner.execute_immediate(
        context_id="ctx-001",
        message=user_msg,
        handler=weather_agent_handler
    )

    print(f"Status:   {task.status.state}")        # TaskState.COMPLETED
    print(f"Response: {reply.get_text()}")
    print(f"Artifact: {task.artifacts[0].data}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 2. Streaming Tasks with Real-Time SSE Chunking

Execute long-running tasks asynchronously while streaming intermediate tokens and status updates:

```python
import asyncio
from a2a.models.message import Message
from a2a.models.task import Task
from a2a.runners.in_memory import InMemoryTaskRunner
from a2a.rpc.sse import format_sse_stream_response

async def streaming_analyst_handler(task: Task, incoming: Message) -> Message:
    # Stream reasoning progress via task event queue
    for progress_pct in [25, 50, 75, 100]:
        await asyncio.sleep(0.05)
        await task.event_queue.put(
            {"type": "status_update", "progress": progress_pct, "message": f"Analyzing data... {progress_pct}%"}
        )
    return Message.from_text("Analysis complete: High efficiency detected.", role="agent", context_id=incoming.context_id)

async def main():
    runner = InMemoryTaskRunner()
    user_msg = Message.from_text("Analyze server telemetry logs.", role="user", context_id="ctx-stream-1")

    # 1. Submit task non-blockingly
    task = await runner.submit_task("ctx-stream-1", user_msg, streaming_analyst_handler)
    print(f"Submitted Task ID: {task.id}")

    # 2. Subscribe to real-time events and format as SSE
    async for event in runner.subscribe_task(task.id):
        sse_chunk = format_sse_stream_response(event)
        print(f"SSE Event:\n{sse_chunk.strip()}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 3. Multimodal Audio Streaming & Video Keyframe Payloads

Work seamlessly with binary audio chunks (e.g. PCM / Opus for Whisper STT) and video frames with spatial bounding-box artifacts:

```python
import asyncio
import numpy as np
from a2a.models.message import Message, AudioPart, VideoPart
from a2a.multimodal.audio import AudioStreamBuffer, chunk_pcm_data
from a2a.multimodal.video import create_bounding_box_artifact

async def main():
    # 1. Generate synthetic 16kHz PCM audio (1 second sine wave)
    sample_rate = 16000
    t = np.linspace(0, 1.0, sample_rate, dtype=np.float32)
    pcm_samples = (np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)
    pcm_bytes = pcm_samples.tobytes()

    # 2. Chunk audio stream into 500ms frames
    buffer = AudioStreamBuffer(sample_rate=sample_rate)
    for chunk in chunk_pcm_data(pcm_bytes, chunk_duration_sec=0.5, sample_rate=sample_rate):
        buffer.add_chunk(AudioPart.from_bytes(chunk, format="pcm", sample_rate=sample_rate))

    print(f"Buffered audio duration: {buffer.total_duration_sec():.2f}s, Bytes: {len(buffer.get_all_bytes())}")

    # 3. Create multimodal message containing text, audio, and video keyframe
    dummy_frame = b"\xFF\xD8\xFF\xE0" + b"\x00" * 60  # Mock JPEG header + payload
    msg = Message(
        role="user",
        parts=[
            AudioPart.from_bytes(pcm_bytes[:3200], format="pcm", sample_rate=16000),
            VideoPart.from_frame_bytes(dummy_frame, mime_type="image/jpeg", frame_number=101),
        ],
        context_id="ctx-multimodal-1"
    )

    # 4. Attach spatial vision annotation artifact
    bbox_artifact = create_bounding_box_artifact(
        name="detected_objects",
        bounding_boxes=[
            {"label": "license_plate", "x_min": 0.42, "y_min": 0.65, "x_max": 0.58, "y_max": 0.73, "confidence": 0.98}
        ],
        frame_number=101
    )
    print(f"Created Vision Artifact: {bbox_artifact.name} with {len(bbox_artifact.data['boxes'])} annotations")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 4. JSON-RPC 2.0 Dispatcher

Route standardized JSON-RPC 2.0 requests with automatic method aliasing (`tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/list`):

```python
import asyncio
from a2a.models.message import Message
from a2a.models.task import Task
from a2a.runners.in_memory import InMemoryTaskRunner
from a2a.rpc.jsonrpc import A2AJsonRpcDispatcher

async def assistant_handler(task: Task, message: Message) -> Message:
    return Message.from_text(f"Echo response to: '{message.get_text()}'", role="agent", context_id=message.context_id)

async def main():
    runner = InMemoryTaskRunner()
    dispatcher = A2AJsonRpcDispatcher(runner=runner, default_handler=assistant_handler)

    # 1. Dispatch tasks/send RPC payload
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "contextId": "ctx-rpc-1",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Deploy release candidate to staging."}]
            }
        },
        "id": "req-101"
    }

    response = await dispatcher.dispatch(request_payload)
    print(f"JSON-RPC 2.0 Response:\n{response}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 5. Durable Distributed Workflows via Temporal

Execute resilient A2A workflows across a Temporal cluster with durable timers, saga compensation, and automatic retry policies:

```python
import asyncio
import os
import uuid
from temporalio.client import Client
from a2a.models.message import Message
from a2a.runners.temporal.client import TemporalTaskRunner

async def main():
    # Connect to Temporal server (local dev server or distributed cluster)
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    client = await Client.connect(temporal_host, namespace="default")

    runner = TemporalTaskRunner(
        client=client,
        task_queue="a2a-task-queue"
    )

    context_id = f"ctx-temporal-{uuid.uuid4().hex[:6]}"
    task_id = f"task-wf-{uuid.uuid4().hex[:6]}"
    user_msg = Message.from_text("Review quarterly financial anomalies.", role="user", context_id=context_id)

    async def worker_placeholder(task, msg):
        pass  # Actual computation is executed by the Temporal Worker fleet

    task, reply = await runner.execute_immediate(
        context_id=context_id,
        message=user_msg,
        handler=worker_placeholder,
        task_id=task_id
    )

    print(f"Temporal Workflow State: {task.status.state}")
    print(f"Worker Response:         {reply.get_text()}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 6. Persistent SQLite Task Storage

Store conversation history, status updates, and multimodal artifacts durably using SQLite:

```python
from a2a.models.message import Message
from a2a.models.artifact import Artifact
from a2a.models.task import TaskState
from a2a.store.sqlite import SQLiteTaskStore

# Initialize store with file-backed SQLite database
store = SQLiteTaskStore(db_path="a2a_tasks.db")

# 1. Create a task
task = store.create_task(
    task_id="task-db-001",
    context_id="ctx-finance",
    initial_message=Message.from_text("Generate balance sheet.", role="user", context_id="ctx-finance")
)

# 2. Update status and add artifacts
store.update_status(task.id, TaskState.WORKING, message="Aggregating accounts...")
store.add_artifact(task.id, Artifact.structured_data("balance_sheet", {"assets": 150000, "liabilities": 50000}))
store.update_status(task.id, TaskState.COMPLETED, message="Balance sheet ready.")

# 3. Retrieve task state
retrieved = store.get_task("task-db-001")
print(f"Retrieved Task State: {retrieved.status.state}")
print(f"Artifacts Attached:   {retrieved.artifacts[0].name} -> {retrieved.artifacts[0].data}")
```

---

## Running the Test Suite

Execute the full suite of unit and integration tests:

```bash
pytest -v
```

All 16 test suites covering runners, storage, models, multimodal codecs, and JSON-RPC dispatchers pass with 100% reliability.

---

## Security & Verification

For end-to-end cryptographic authentication, Ed25519 decentralized identifiers (DIDs), forward-secret ChaCha20-Poly1305 encryption, and Merkle audit receipts, use the companion security layer:
👉 [**talosprotocol/talos-a2a**](https://github.com/talosprotocol/talos-a2a)

---

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
