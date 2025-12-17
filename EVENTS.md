# Event System Architecture

This document details the complete event and execution trace system in the Amplifier platform, covering backend hooks, SSE streaming, session files, and frontend trace visualization.

## Overview

The Amplifier platform uses two parallel event systems:

1. **Global Events** - Session lifecycle events (created, updated, deleted)
2. **Session Events** - Execution events within a session (tool calls, thinking, messages)

Both systems use Server-Sent Events (SSE) for real-time streaming to the frontend.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (amplifierd)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐    ┌─────────────────────────────────────────────┐   │
│  │  amplifier_core  │    │           SessionStreamManager              │   │
│  │  ExecutionRunner │    │  ┌─────────────────────────────────────┐   │   │
│  │                  │───▶│  │  StreamingHookRegistry              │   │   │
│  │  (runs agent     │    │  │  - wraps HookRegistry               │   │   │
│  │   execution)     │    │  │  - emits to EventQueueEmitter       │   │   │
│  └──────────────────┘    │  └─────────────────────────────────────┘   │   │
│           │              │  ┌─────────────────────────────────────┐   │   │
│           │              │  │  ExecutionTraceHook                 │   │   │
│           ▼              │  │  - persists to execution_trace.jsonl│   │   │
│  ┌──────────────────┐    │  └─────────────────────────────────────┘   │   │
│  │  HookRegistry    │    │  ┌─────────────────────────────────────┐   │   │
│  │  (from core)     │    │  │  EventQueueEmitter                  │   │   │
│  │  - tool:pre      │    │  │  - multi-subscriber async queues    │───┼───┼──▶ SSE
│  │  - tool:post     │    │  │  - fan-out to all subscribers       │   │   │
│  │  - thinking:delta│    │  └─────────────────────────────────────┘   │   │
│  │  - etc.          │    └─────────────────────────────────────────────┘   │
│  └──────────────────┘                                                       │
│                                                                             │
│  Session Files (per session):                                              │
│  ~/.amplifierd/state/sessions/{session_id}/                                │
│    ├── events.jsonl           # Full amplifier_core event log              │
│    ├── transcript.jsonl       # User/assistant messages only               │
│    └── execution_trace.jsonl  # Turn-by-turn trace for UI                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ SSE Connections
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (webapp)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐   │
│  │  useGlobalEvents   │  │  useEventStream    │  │  useExecutionState │   │
│  │  /api/v1/events    │  │  /sessions/{}/stream│  │  /execution-trace  │   │
│  │  - session:created │  │  - hook:tool:pre   │  │  - historical data │   │
│  │  - session:updated │  │  - hook:tool:post  │  │  - live updates    │   │
│  └────────────────────┘  │  - hook:thinking   │  └────────────────────┘   │
│                          └────────────────────┘            │               │
│                                    │                       │               │
│                                    ▼                       ▼               │
│                          ┌─────────────────────────────────────────────┐   │
│                          │              ExecutionPanel                 │   │
│                          │  ┌─────────────────────────────────────┐   │   │
│                          │  │  TurnsList                          │   │   │
│                          │  │  └── TurnItem (per turn)            │   │   │
│                          │  │      └── ToolTraceList              │   │   │
│                          │  └─────────────────────────────────────┘   │   │
│                          └─────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Components

### 1. StreamingHookRegistry

**File**: `amplifierd/amplifierd/hooks/__init__.py`

A decorator pattern that wraps the amplifier_core `HookRegistry` to add SSE streaming capability. When hooks fire, events are emitted both to the original registry and to an `EventQueueEmitter` for SSE delivery.

```python
DEFAULT_STREAMING_HOOKS = {
    "tool:pre",
    "tool:post",
    "content_block:start",
    "content_block:end",
    "thinking:delta",
    "approval:required",
    "approval:granted",
    "approval:denied",
    "assistant_message:start",
    "assistant_message:complete",
}
```

**Key Methods**:
- `register(event, handler)` - Registers a handler for an event
- `emit(event, data)` - Fires event to all handlers AND streams to SSE
- `mount_to(coordinator)` - Attaches to ExecutionRunner's coordinator

**Event Prefixing**: When emitting to SSE, events are prefixed with `hook:` (e.g., `tool:pre` becomes `hook:tool:pre`).

### 2. ExecutionTraceHook

**File**: `amplifierd/amplifierd/hooks/execution_trace.py`

Persists execution traces to JSONL for historical analysis. Tracks complete turn cycles including tool calls, thinking blocks, and timing.

**Data Models** (with camelCase serialization for frontend compatibility):

```python
class TraceTool(BaseModel):
    id: str
    name: str
    parallel_group_id: str = Field(serialization_alias="parallelGroupId")
    status: str  # "starting", "running", "completed", "error"
    start_time: int = Field(serialization_alias="startTime")
    end_time: int | None = Field(serialization_alias="endTime")
    duration: float | None
    arguments: dict | None
    result: str | None  # Truncated to 1000 chars
    error: str | None
    is_sub_agent: bool = Field(serialization_alias="isSubAgent")
    sub_agent_name: str | None = Field(serialization_alias="subAgentName")

class TraceTurn(BaseModel):
    id: str
    user_message: str = Field(serialization_alias="userMessage")
    status: str  # "active", "completed"
    start_time: int = Field(serialization_alias="startTime")
    end_time: int | None = Field(serialization_alias="endTime")
    tools: list[TraceTool]
    thinking: list[TraceThinking]
```

**Hook Events Handled**:
- `assistant_message:start` - Creates new turn
- `tool:pre` - Adds tool to current turn
- `tool:post` - Updates tool with result/timing
- `thinking:delta` - Records thinking block
- `assistant_message:complete` - Saves turn to JSONL

### 3. EventQueueEmitter

**File**: `amplifierd/amplifierd/streaming.py`

Multi-subscriber async queue system for SSE event distribution.

```python
class EventQueueEmitter:
    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Create new subscriber queue."""
        queue = asyncio.Queue()
        self._queues.add(queue)
        return queue

    async def emit(self, event_type: str, data: dict):
        """Fan-out event to all subscriber queues."""
        for queue in self._queues:
            await queue.put({"event": event_type, "data": data})

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove subscriber queue."""
        self._queues.discard(queue)
```

### 4. SessionStreamManager

**File**: `amplifierd/amplifierd/services/session_stream_manager.py`

Coordinates all streaming infrastructure for a single session.

**Creates and Manages**:
- `EventQueueEmitter` - For SSE event distribution
- `StreamingHookRegistry` - Wraps amplifier_core hooks
- `ExecutionTraceHook` - Persists trace to JSONL

**Key Method**:
```python
def mount_hooks(self, coordinator: ModuleCoordinator):
    """Mount streaming hooks to execution runner's coordinator."""
    self.hook_registry.mount_to(coordinator)
```

### 5. SessionStreamRegistry

**File**: `amplifierd/amplifierd/services/session_stream_registry.py`

Global singleton registry mapping session IDs to their StreamManagers.

```python
class SessionStreamRegistry:
    _managers: dict[str, SessionStreamManager] = {}

    def get_or_create(self, session_id: str, session_dir: Path) -> SessionStreamManager
    def get(self, session_id: str) -> SessionStreamManager | None
    def remove(self, session_id: str)
```

### 6. GlobalEventService

**File**: `amplifierd/amplifierd/services/global_events.py`

Singleton service for application-wide events (session lifecycle).

```python
class GlobalEventService:
    _emitter = EventQueueEmitter()

    async def emit_session_created(self, session_id: str, project_id: str)
    async def emit_session_updated(self, session_id: str, project_id: str, fields: list[str])
```

---

## API Endpoints

### Session SSE Stream

**Endpoint**: `GET /api/v1/sessions/{session_id}/stream`
**File**: `amplifierd/amplifierd/routers/stream.py`

Creates persistent SSE connection for real-time session events.

**Event Types Streamed**:
- `connected` - Initial connection confirmation
- `keepalive` - Periodic heartbeat (every 15s)
- `hook:tool:pre` - Tool execution starting
- `hook:tool:post` - Tool execution complete
- `hook:thinking:delta` - Thinking content
- `hook:assistant_message:start` - Turn starting
- `hook:assistant_message:complete` - Turn complete
- `hook:content_block:start/end` - Content blocks
- `hook:approval:*` - Approval events

**SSE Format**:
```
event: hook:tool:pre
data: {"tool_name": "Read", "tool_input": {...}, "parallel_group_id": "..."}

event: keepalive
data: {}
```

### Global Events Stream

**Endpoint**: `GET /api/v1/events`
**File**: `amplifierd/amplifierd/routers/events.py`

Global SSE stream for session lifecycle events.

**Event Types**:
- `session:created` - New session created
- `session:updated` - Session metadata changed (e.g., read state)

### Execution Trace

**Endpoint**: `GET /api/v1/sessions/{session_id}/execution-trace`
**File**: `amplifierd/amplifierd/routers/sessions.py`

Returns historical execution trace for a session.

**Response**:
```json
{
  "turns": [
    {
      "id": "uuid",
      "userMessage": "...",
      "status": "completed",
      "startTime": 1234567890000,
      "endTime": 1234567891000,
      "tools": [...],
      "thinking": [...]
    }
  ]
}
```

### Send Message

**Endpoint**: `POST /api/v1/sessions/{session_id}/messages/send-message`
**File**: `amplifierd/amplifierd/routers/messages.py`

Sends user message and triggers execution. This is where hooks get mounted and events start flowing.

**Flow**:
1. Get/create SessionStreamManager
2. Get ExecutionRunner
3. Mount hooks to runner's coordinator
4. Emit `hook:assistant_message:start`
5. Execute in background task
6. Background emits tool events as they occur
7. Emit `hook:assistant_message:complete` when done

---

## Session Files

Each session stores data in: `~/.amplifierd/state/sessions/{session_id}/`

### events.jsonl

**Purpose**: Complete amplifier_core event log
**Format**: One JSON object per line
**Content**: All events from the execution runner (verbose, includes internal events)

```json
{"type": "assistant_message:start", "data": {...}, "timestamp": "..."}
{"type": "tool:pre", "data": {"tool_name": "Read", ...}, "timestamp": "..."}
{"type": "content_block:start", "data": {...}, "timestamp": "..."}
```

**Usage**: Debugging, complete audit trail

### transcript.jsonl

**Purpose**: User and assistant messages only
**Format**: One JSON object per line
**Content**: Clean conversation history

```json
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "timestamp": "..."}
```

**Usage**: Chat history display, conversation export

### execution_trace.jsonl

**Purpose**: Turn-by-turn execution trace for UI
**Format**: One JSON object per line (one per turn)
**Content**: Structured turn data with tools and thinking

```json
{
  "id": "uuid",
  "userMessage": "...",
  "status": "completed",
  "startTime": 1234567890000,
  "endTime": 1234567891000,
  "tools": [
    {
      "id": "tool-uuid",
      "name": "Read",
      "parallelGroupId": "...",
      "status": "completed",
      "startTime": 1234567890100,
      "endTime": 1234567890500,
      "duration": 400.0,
      "arguments": {"file_path": "..."},
      "result": "file contents...",
      "isSubAgent": false
    }
  ],
  "thinking": [
    {"id": "...", "content": "...", "timestamp": 1234567890050}
  ]
}
```

**Usage**: ExecutionPanel trace visualization

---

## Frontend Components

### useGlobalEvents

**File**: `webapp/src/hooks/useGlobalEvents.ts`

Subscribes to global event stream at app root.

```typescript
useEffect(() => {
  const eventSource = new EventSource(`${BASE_URL}/api/v1/events`);

  eventSource.addEventListener('session:created', (e) => {
    queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
    queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
  });

  eventSource.addEventListener('session:updated', (e) => {
    // Update cached session data, invalidate queries
  });

  return () => eventSource.close();
}, []);
```

### useEventStream

**File**: `webapp/src/features/session/hooks/useEventStream.ts`

Manages SSE connection to session stream.

**Features**:
- Creates EventSource to `/sessions/{id}/stream`
- Registers listeners for each hook event type
- Calls callbacks (onToolStart, onToolComplete, etc.)
- Handles reconnection on error

**Event Mapping**:
```typescript
eventSource.addEventListener('hook:tool:pre', handler);
eventSource.addEventListener('hook:tool:post', handler);
eventSource.addEventListener('hook:thinking:delta', handler);
eventSource.addEventListener('hook:assistant_message:start', handler);
eventSource.addEventListener('hook:assistant_message:complete', handler);
```

### useExecutionState

**File**: `webapp/src/features/session/hooks/useExecutionState.ts`

Manages execution trace state for the UI.

**Features**:
- Loads historical trace via TanStack Query (`/execution-trace`)
- Maintains current turn state in refs (avoids re-render churn during SSE)
- Provides callbacks for SSE event handlers
- Calculates metrics (total tools, avg duration, etc.)

**Key Pattern** - Uses refs with forced updates:
```typescript
const stateRef = useRef<ExecutionState>({ turns: [], currentTurn: null, metrics: {...} });
const [updateCounter, setUpdateCounter] = useState(0);
const forceUpdate = useCallback(() => setUpdateCounter(c => c + 1), []);

// Load historical data
useEffect(() => {
  if (historicalTrace?.turns && !initializedRef.current) {
    stateRef.current.turns = historicalTrace.turns;
    initializedRef.current = true;
    forceUpdate(); // Trigger re-render to show data
  }
}, [historicalTrace, forceUpdate]);
```

**API**:
```typescript
{
  getState: () => ExecutionState,
  startTurn: (userMessage: string) => void,
  completeTurn: () => void,
  addTool: (name, input, parallelGroupId) => void,
  updateTool: (name, parallelGroupId, updates) => void,
  addThinking: (content: string) => void,
  getCurrentActivity: () => CurrentActivity | null,
}
```

### ExecutionPanel

**File**: `webapp/src/features/session/components/ExecutionPanel.tsx`

Main container for trace visualization.

**Props**:
- `executionState`: From useExecutionState
- `isStreaming`: Whether execution is in progress

**Renders**:
- Activity indicator (current tool/thinking)
- TurnsList with all turns
- Session metrics

### TurnsList / TurnItem

**Files**:
- `webapp/src/features/session/components/TurnsList.tsx`
- `webapp/src/features/session/components/TurnItem.tsx`

Renders the list of execution turns.

**TurnItem displays**:
- Turn status (active/completed/error)
- User message (truncated in header)
- Duration
- Tool count
- Expandable details with:
  - Full user message
  - ToolTraceList
  - Thinking blocks

### ToolTraceList

**File**: `webapp/src/features/session/components/ToolTraceList.tsx`

Renders tool calls within a turn.

**Displays**:
- Tool name and status icon
- Duration
- Expandable arguments/results
- Sub-agent indicator (Task tool)
- Parallel group visualization

---

## Data Flow

### Live Execution Flow

```
1. User sends message via POST /send-message
   │
2. Backend creates/gets SessionStreamManager
   │
3. StreamingHookRegistry mounted to ExecutionRunner
   │
4. Emit hook:assistant_message:start
   │
5. amplifier_core executes (tools, thinking, etc.)
   │  Each hook event:
   │  ├── StreamingHookRegistry.emit()
   │  │   ├── Original HookRegistry handlers
   │  │   └── EventQueueEmitter.emit() → SSE queues
   │  │
   │  └── ExecutionTraceHook handlers
   │      └── Build current turn in memory
   │
6. Frontend receives SSE events
   │  ├── useEventStream receives hook:tool:pre
   │  └── Calls executionState.addTool()
   │      └── Updates ref + forceUpdate()
   │          └── ExecutionPanel re-renders
   │
7. Emit hook:assistant_message:complete
   │
8. ExecutionTraceHook saves turn to execution_trace.jsonl
```

### Historical Load Flow

```
1. User opens session page
   │
2. useExecutionState queries GET /execution-trace
   │
3. Backend reads execution_trace.jsonl
   │  └── Returns { turns: [...] }
   │
4. useEffect detects historicalTrace
   │  └── stateRef.current.turns = historicalTrace.turns
   │  └── forceUpdate()
   │
5. ExecutionPanel renders with historical turns
```

---

## Troubleshooting

### Events not appearing in trace

1. **Check execution_trace.jsonl exists**:
   ```bash
   cat ~/.amplifierd/state/sessions/{session_id}/execution_trace.jsonl
   ```

2. **Check API returns data**:
   ```bash
   curl http://localhost:8420/api/v1/sessions/{session_id}/execution-trace
   ```

3. **Check frontend console** for useExecutionState logs

4. **Verify hooks are mounted** - check daemon logs for "Hook fired:" messages

### SSE connection issues

1. **Check network tab** for `/stream` connection status
2. **Verify CORS** - check daemon CORS configuration
3. **Check for keepalive** - should see keepalive events every 15s

### Data format mismatches

1. **Backend uses camelCase** via Pydantic `serialization_alias` and `by_alias=True`
2. **Frontend TypeScript types** must match (e.g., `parallelGroupId` not `parallel_group_id`)
3. **Check for null handling** - defensive `?? ''` for optional fields

---

## Configuration

### Daemon Configuration

**File**: `~/.amplifierd/config/daemon.yaml`

```yaml
# SSE keepalive interval
sse_keepalive_seconds: 15

# Hook event types to stream (can customize)
streaming_hooks:
  - tool:pre
  - tool:post
  - thinking:delta
  # ... etc
```

### CORS (for LAN access)

**File**: `amplifierd/amplifierd/__main__.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Version: Single Source of Truth

### Current Problem

We have two files storing overlapping data:

| File | Written By | Contains |
|------|------------|----------|
| `events.jsonl` | hooks-logging (amplifier_core) | All events including tool:pre, tool:post, thinking:delta |
| `execution_trace.jsonl` | ExecutionTraceHook (amplifierd) | Aggregated turns with tools/thinking |

This creates:
- Duplicate storage
- Potential sync issues
- Two codepaths to maintain
- A bug in ExecutionTraceHook causing duplicate tool entries

### Planned Changes

**Goal**: Use `events.jsonl` as the single source of truth. Generate trace view on-the-fly.

#### 1. Remove ExecutionTraceHook

**Delete**:
- `amplifierd/amplifierd/hooks/execution_trace.py`
- References in `amplifierd/amplifierd/hooks/__init__.py`
- Registration in `amplifierd/amplifierd/services/session_stream_manager.py`

#### 2. Update `/execution-trace` Endpoint

**File**: `amplifierd/amplifierd/routers/sessions.py`

Change from reading `execution_trace.jsonl` to aggregating from `events.jsonl`:

```python
@router.get("/{session_id}/execution-trace")
async def get_execution_trace(session_id: str, ...):
    # Read events.jsonl
    events_file = state_dir / "sessions" / session_id / "events.jsonl"

    # Aggregate into turns
    turns = aggregate_events_to_turns(events_file)

    return {"turns": turns}
```

#### 3. Aggregation Logic

Parse events.jsonl and group into turns:

```python
def aggregate_events_to_turns(events_file: Path) -> list[dict]:
    """Aggregate raw events into UI-friendly turns."""
    turns = []
    current_turn = None

    for event in read_jsonl(events_file):
        event_type = event.get("event")
        data = event.get("data", {})

        if event_type == "prompt:submit":
            # Start new turn
            current_turn = {
                "id": str(uuid4()),
                "userMessage": data.get("prompt", ""),
                "status": "active",
                "startTime": parse_timestamp(event["ts"]),
                "tools": [],
                "thinking": [],
            }

        elif event_type == "tool:pre" and current_turn:
            current_turn["tools"].append({
                "id": data.get("parallel_group_id", str(uuid4())),
                "name": data.get("tool_name", ""),
                "parallelGroupId": data.get("parallel_group_id", ""),
                "status": "running",
                "startTime": parse_timestamp(event["ts"]),
                "arguments": data.get("tool_input"),
            })

        elif event_type == "tool:post" and current_turn:
            # Find and update matching tool
            tool = find_tool(current_turn["tools"], data)
            if tool:
                tool["status"] = "completed"
                tool["endTime"] = parse_timestamp(event["ts"])
                tool["duration"] = tool["endTime"] - tool["startTime"]
                tool["result"] = truncate(str(data.get("result", "")), 1000)

        elif event_type == "thinking:delta" and current_turn:
            current_turn["thinking"].append({
                "id": str(uuid4()),
                "content": data.get("delta", ""),
                "timestamp": parse_timestamp(event["ts"]),
            })

        elif event_type == "session:end" and current_turn:
            # Complete turn
            current_turn["status"] = "completed"
            current_turn["endTime"] = parse_timestamp(event["ts"])
            turns.append(current_turn)
            current_turn = None

    return turns
```

#### 4. Delete Stale Files

Remove `execution_trace.jsonl` from existing sessions (optional cleanup).

### Benefits

1. **Single source of truth** - No sync issues
2. **Simpler codebase** - Remove ExecutionTraceHook entirely
3. **Flexible** - Change trace format without re-processing historical data
4. **Bug-free** - Eliminates duplicate tool entry bug
5. **Raw data preserved** - Full event log available for debugging

### Migration Path

1. Implement aggregation function
2. Update `/execution-trace` endpoint
3. Remove ExecutionTraceHook
4. Test with existing sessions (backwards compatible - events.jsonl already has data)
5. Optionally clean up old `execution_trace.jsonl` files
