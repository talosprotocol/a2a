# Talos Protocol Agent-to-Agent (A2A) Engine Specification

**Document Version:** 1.0.0  
**Status:** Implemented  
**Repository:** `talosprotocol/a2a`

---

## 1. Executive Overview

The Talos A2A Engine provides a unified, transport-agnostic, and execution-agnostic communication protocol for autonomous AI agents. It standardizes task lifecycle management, blocking request-reply interactions, real-time Server-Sent Events (SSE) streaming, and multimodal payload exchange across arbitrary agent runtimes.

---

## 2. Core Protocol Architecture

```
                  +--------------------------------+
                  |       A2A Client / Agent       |
                  +---------------+----------------+
                                  |
                   JSON-RPC 2.0 / SSE Transport
                                  |
                  +---------------v----------------+
                  |     A2AJsonRpcDispatcher       |
                  +---------------+----------------+
                                  |
              +-------------------+-------------------+
              |                                       |
      +-------v-------+                       +-------v-------+
      | InMemoryRunner|                       | TemporalRunner|
      | (Sub-millisecond                      | (Distributed, |
      |  local queues)|                       |  durable SAGAs|
      +-------+-------+                       +-------+-------+
              |                                       |
              +-------------------+-------------------+
                                  |
                  +---------------v----------------+
                  |    Task Store (Memory/SQLite)  |
                  +--------------------------------+
```

### 2.1 Transport Layer
- **Protocol:** JSON-RPC 2.0 over HTTP POST / WebSocket.
- **Streaming:** Server-Sent Events (`text/event-stream`) delivering chunked text, audio deltas, or task status updates with strict monotonic event IDs.
- **Endpoints:**
  - `tasks/send`: Initiates or queues a task (blocking or non-blocking).
  - `tasks/get`: Polls current task state, outputs, and artifacts.
  - `tasks/cancel`: Issues cooperative or preemptive task cancellation.
  - `tasks/stream`: Establishes SSE stream connection for real-time progress.

### 2.2 Execution Engines (Runners)
1. **InMemoryTaskRunner:**
   - Designed for local micro-agents, testing, and ultra-low-latency interactions (<5ms).
   - In-memory event dispatching and task lifecycle tracking without external infrastructure.
2. **TemporalTaskRunner:**
   - Designed for long-running, fault-tolerant, multi-day swarms and external API workflows.
   - Powered by Temporal workflows (`A2ATaskWorkflow`) and activities (`execute_task_activity`).
   - Automatically handles retries, heartbeats, network partitions, and host restarts.

---

## 3. Multimodal Payload Primitives

All messages conform to the extensible `Message` model comprising heterogeneous parts:

```json
{
  "role": "user | agent",
  "parts": [
    {
      "type": "text",
      "text": "Analyze security perimeter."
    },
    {
      "type": "audio",
      "encoding": "pcm_s16le | opus",
      "sample_rate": 16000,
      "channels": 1,
      "data_base64": "<base64>"
    },
    {
      "type": "video",
      "format": "mp4 | jpeg_frames",
      "fps": 30.0,
      "keyframes": ["<base64_frame_1>", "<base64_frame_2>"]
    }
  ]
}
```

### 3.1 Streaming Audio & Video Artifacts
- **`AudioStreamBuffer`:** Manages rolling chunked audio buffers for live voice interactions, performing real-time PCM chunking and timestamp reassembly.
- **`BoundingBoxArtifact` & `KeyframeArtifact`:** Encapsulates spatial detection boxes and visual grounding data produced during agent visual processing.

---

## 4. State Management & Persistence

- **Task States:** `PENDING` -> `RUNNING` -> `COMPLETED` / `FAILED` / `CANCELLED`.
- **Storage Backends:**
  - `InMemoryTaskStore`: Ephemeral dictionary store.
  - `SqliteTaskStore`: ACID-compliant SQLite store for persistent edge nodes (e.g. Raspberry Pi).
