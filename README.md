# talosprotocol/a2a

Universal, protocol-pure **Agent-to-Agent (A2A) v1** runtime engine supporting pluggable execution drivers (**In-Memory** & **Temporal**), blocking & streaming delivery modes, and multimodal payloads (**Text**, **Voice**, **Video**).

## Features

- **Protocol-Pure A2A v1 Compliance**: Full implementation of canonical A2A task lifecycles, states (`SUBMITTED`, `WORKING`, `COMPLETED`, `FAILED`, `CANCELED`), messages, and artifacts.
- **Dual Execution Drivers**:
  - `InMemoryTaskRunner`: High-throughput, zero-dependency, local asyncio queues and events for edge instances (Raspberry Pi, mobile, IoT) and tests.
  - `TemporalTaskRunner`: Durable, distributed workflow execution with automatic retries, cross-node task queues, saga compensation, and event updates.
- **Flexible Invocation Modes**:
  - **Blocking (Immediate)**: Low-latency synchronous dispatch.
  - **Non-blocking (Submit)**: Asynchronous task queuing with polling or barrier wait.
  - **Streaming**: Real-time chunked status updates, reasoning traces (`<think>`), and multimodal tokens.
- **First-Class Multimodal Payloads**:
  - `TextPart`: Natural language, prompt instructions, structured JSON/YAML.
  - `AudioPart`: Streaming PCM / Opus audio chunks for conversational speech.
  - `VideoPart`: Keyframes, video segments, and spatial bounding-box annotations.
- **JSON-RPC 2.0 & SSE Transports**: Canonical dispatchers for agent discovery, task subscription, and execution.
