# Event System

The amplifierd event system uses a single file (`events.jsonl`) as the source of truth for all session activity. This file is written by amplifier_core's hooks-logging module and read on-demand for trace visualization.

## Architecture

```
amplifier_core (hooks-logging)
        │
        ▼
   events.jsonl  ◄── Single source of truth
        │
        ▼
  trace_aggregator.py  ◄── On-the-fly aggregation
        │
        ▼
   /execution-trace API  ◄── Frontend consumption
```

## Event File

**Location**: `{state_dir}/sessions/{session_id}/events.jsonl`

Each line is a JSON object with:

```json
{
  "event": "event_type",
  "ts": "2025-12-17T20:21:22.794+00:00",
  "data": { ... }
}
```

## Event Types

### prompt:submit

Marks the start of a new turn (user message submitted).

```json
{
  "event": "prompt:submit",
  "ts": "...",
  "data": {
    "prompt": "User's message text"
  }
}
```

### tool:pre

Emitted before a tool executes.

```json
{
  "event": "tool:pre",
  "ts": "...",
  "data": {
    "tool_name": "read_file",
    "tool_input": { "file_path": "/path/to/file" },
    "parallel_group_id": "uuid-for-parallel-calls"
  }
}
```

### tool:post

Emitted after a tool completes.

```json
{
  "event": "tool:post",
  "ts": "...",
  "data": {
    "tool_name": "read_file",
    "parallel_group_id": "uuid-for-parallel-calls",
    "result": {
      "success": true,
      "output": "file contents..."
    }
  }
}
```

For errors:

```json
{
  "event": "tool:post",
  "ts": "...",
  "data": {
    "tool_name": "read_file",
    "parallel_group_id": "uuid-for-parallel-calls",
    "result": {
      "success": false,
      "error": {
        "message": "File not found"
      }
    }
  }
}
```

### thinking:delta

Streaming thinking content from the model.

```json
{
  "event": "thinking:delta",
  "ts": "...",
  "data": {
    "delta": "Let me think about this..."
  }
}
```

### session:end

Marks the end of a turn.

```json
{
  "event": "session:end",
  "ts": "...",
  "data": {}
}
```

## Trace Aggregation

The `/api/v1/sessions/{session_id}/execution-trace` endpoint aggregates events.jsonl into structured turns:

```python
from amplifierd.services.trace_aggregator import aggregate_events_to_turns

turns = aggregate_events_to_turns(events_file)
```

### Aggregation Logic

1. `prompt:submit` → Creates new `TraceTurn`
2. `tool:pre` → Adds `TraceTool` to current turn (status: running)
3. `tool:post` → Updates matching tool with result/error and timing
4. `thinking:delta` → Adds `TraceThinking` to current turn
5. `session:end` → Marks turn as completed

### Matching tool:pre to tool:post

Tools are matched by `tool_name` + `parallel_group_id`. This handles parallel tool calls correctly.

## Data Models

### TraceTurn

```python
class TraceTurn(BaseModel):
    id: str
    user_message: str          # serialized as "userMessage"
    status: str                # "active" | "completed"
    start_time: int            # serialized as "startTime" (ms since epoch)
    end_time: int | None       # serialized as "endTime"
    tools: list[TraceTool]
    thinking: list[TraceThinking]
```

### TraceTool

```python
class TraceTool(BaseModel):
    id: str
    name: str
    parallel_group_id: str     # serialized as "parallelGroupId"
    status: str                # "starting" | "running" | "completed" | "error"
    start_time: int            # serialized as "startTime"
    end_time: int | None       # serialized as "endTime"
    duration: float | None     # milliseconds
    arguments: dict | None
    result: str | None
    error: str | None
    is_sub_agent: bool         # serialized as "isSubAgent"
    sub_agent_name: str | None # serialized as "subAgentName"
```

### TraceThinking

```python
class TraceThinking(BaseModel):
    id: str
    content: str
    timestamp: int
```

## SSE Streaming

Real-time events are streamed via SSE through `StreamingHookRegistry`, which wraps the session's hook registry and emits events to connected clients:

- `hook:tool:pre` - Tool starting
- `hook:tool:post` - Tool completed
- `hook:thinking:delta` - Thinking content
- `hook:approval:required` - User approval needed

The SSE stream provides live updates while events.jsonl provides the persistent record.
