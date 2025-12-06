# Amplifier Orchestrators Guide

**Comprehensive guide for understanding and working with Amplifier orchestrators**

---

## Table of Contents

1. [What Are Orchestrators?](#what-are-orchestrators)
2. [How Orchestrators Work](#how-orchestrators-work)
3. [Available Orchestrators](#available-orchestrators)
4. [Orchestrator Contract](#orchestrator-contract)
5. [Configuration](#configuration)
6. [Execution Flow](#execution-flow)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Reference](#reference)

---

## What Are Orchestrators?

An **Orchestrator** (also called a "loop") is the component responsible for the agent execution loop. It coordinates the flow between user input, LLM calls, tool execution, and response delivery.

### Key Responsibilities

- **Execution loop**: Managing the turn-by-turn conversation flow
- **Provider coordination**: Calling LLM providers with context
- **Tool execution**: Handling tool calls from the LLM
- **Response delivery**: Streaming or batch response to user
- **Error handling**: Managing failures and retries
- **Iteration limits**: Preventing infinite loops

### Philosophy

Orchestrators embody the "execution mechanism" principle:
- **Kernel responsibility**: The orchestrator IS the agent loop
- **Session-scoped**: One orchestrator per session
- **Pluggable implementations**: Different strategies for different needs
- **Simple contract**: Execute prompt, return response

Think of it as: **The orchestrator is the agent's brain stem - automatic execution flow.**

---

## How Orchestrators Work

### The Lifecycle

```
┌─────────────────────┐
│  1. User Prompt     │  User input received
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Add to Context  │  Store user message
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Call Provider   │  Get LLM response
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Tool Calls?     │  Check for tool_use
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
  No │           │ Yes
     │           │
     │     ┌─────▼──────────┐
     │     │ 5. Execute     │  Run tools in parallel
     │     │    Tools       │  (loop-streaming only)
     │     └─────┬──────────┘
     │           │
     │     ┌─────▼──────────┐
     │     │ 6. Add Results │  Store tool_result messages
     │     └─────┬──────────┘
     │           │
     │     ┌─────▼──────────┐
     │     │ 7. Continue    │  Call provider again
     │     └─────┬──────────┘
     │           │
     └─────┬─────┘
           │
┌──────────▼──────────┐
│  8. Return Response │  Deliver to user
└─────────────────────┘
```

### Integration with Session

```python
from amplifier_core import AmplifierSession

# Orchestrator specified in mount plan
mount_plan = {
    "session": {
        "orchestrator": "loop-streaming",  # ← Orchestrator
        "orchestrator_source": "git+https://...",
        "context": "context-simple"
    }
}

async with AmplifierSession(config=mount_plan) as session:
    # Orchestrator handles the entire loop
    response = await session.execute("Read /data/test.txt")
    # Orchestrator:
    # 1. Added user message to context
    # 2. Called provider (got tool_use)
    # 3. Executed read_file tool
    # 4. Called provider again (got text response)
    # 5. Returned final response
```

---

## Available Orchestrators

### loop-basic

**Simple sequential execution loop.**

**Best for:**
- Testing and development
- Batch processing
- Non-interactive use cases
- Debugging (deterministic execution)

**Configuration:**
```yaml
session:
  orchestrator: loop-basic
  orchestrator_source: git+https://github.com/microsoft/amplifier-module-loop-basic@main

orchestrator:
  config:
    max_iterations: 10   # Prevent infinite loops (default: -1 = unlimited)
    timeout: 300         # Timeout in seconds (default: 300)
```

**Execution characteristics:**
- **Sequential tool execution**: Tools run one at a time
- **Batch response**: Returns complete response after all iterations
- **Deterministic**: Same input → same execution order
- **Simple error handling**: Fail fast on errors

**Flow:**
```
User prompt
  → LLM call
    → Tool 1 executes (wait)
      → Tool 2 executes (wait)
        → LLM call
          → Return complete response
```

---

### loop-streaming

**Token-level streaming with parallel tool execution.**

**Best for:**
- Interactive CLI applications
- Web UIs with progressive rendering
- Real-time user feedback
- Long-form content generation

**Configuration:**
```yaml
session:
  orchestrator: loop-streaming
  orchestrator_source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main

orchestrator:
  config:
    buffer_size: 10      # Tokens to buffer before flush (default: 10)
    max_iterations: -1   # Unlimited iterations (default)
    timeout: 300         # Timeout in seconds
```

**Execution characteristics:**
- **Token streaming**: LLM response delivered token-by-token
- **Parallel tool execution**: Multiple tools run concurrently
- **Progressive rendering**: User sees response as it's generated
- **Deterministic context**: Results added in original order (despite parallel execution)
- **Interruptible**: Can stop generation mid-stream

**Flow:**
```
User prompt
  → LLM call (streaming)
    → Token 1 → User
    → Token 2 → User
    → tool_use detected
      → Tool 1 starts ─┐
      → Tool 2 starts ─┤ (parallel)
      → Tool 3 starts ─┘
      → Wait for all
      → Add results (original order)
    → LLM call (streaming)
      → Tokens → User
```

---

### loop-events

**Event-driven orchestration with observability hooks.**

**Best for:**
- Production deployments
- Monitoring and logging
- Custom event handling
- Complex workflows

**Configuration:**
```yaml
session:
  orchestrator: loop-events
  orchestrator_source: git+https://github.com/microsoft/amplifier-module-loop-events@main

orchestrator:
  config:
    max_iterations: 20   # Conservative limit for production
    timeout: 300
    emit_events: true    # Enable event emission (default: true)
```

**Execution characteristics:**
- **Event emission**: Fires hooks at every stage
- **Observable**: Full visibility into execution flow
- **Production-ready**: Robust error handling and recovery
- **Metrics-friendly**: Events enable performance tracking

**Events emitted:**
- `orchestrator:iteration:start`
- `orchestrator:provider:call`
- `orchestrator:tool:execute`
- `orchestrator:iteration:complete`
- `orchestrator:error`

**Flow:**
```
User prompt
  → Event: iteration:start
    → LLM call
      → Event: provider:call
        → tool_use detected
          → Event: tool:execute (per tool)
            → Tools run
          → Event: tool:complete
      → Event: provider:response
  → Event: iteration:complete
```

---

### Comparison Matrix

| Feature | loop-basic | loop-streaming | loop-events |
|---------|-----------|---------------|------------|
| **Tool execution** | Sequential | Parallel | Parallel |
| **Response delivery** | Batch | Streaming | Streaming |
| **Interruptible** | No | Yes | Yes |
| **Events** | No | No | Yes |
| **Best for** | Testing | Interactive | Production |
| **Complexity** | Lowest | Medium | Highest |
| **Observability** | None | Basic | Full |

---

## Orchestrator Contract

### Mount Function

Every orchestrator must implement:

```python
async def mount(coordinator, config: dict):
    """
    Mount the orchestrator.

    Args:
        coordinator: The session coordinator
        config: Configuration from mount plan

    Returns:
        Optional cleanup function
    """
    orchestrator = MyOrchestrator(coordinator, config)
    coordinator.orchestrator = orchestrator

    # Optional: return cleanup function
    async def cleanup():
        await orchestrator.shutdown()

    return cleanup
```

### Required Methods

```python
class Orchestrator:
    async def execute(self, prompt: str) -> str:
        """
        Execute user prompt, return assistant response.

        Args:
            prompt: User input

        Returns:
            Assistant's final response

        Orchestrator responsibilities:
        1. Add user message to context
        2. Loop: Call provider, execute tools, repeat
        3. Return when no more tool calls
        """
        pass

    async def stream_execute(self, prompt: str) -> AsyncIterator[str]:
        """
        Execute with streaming (optional, for streaming loops).

        Args:
            prompt: User input

        Yields:
            Response tokens as generated
        """
        pass
```

### Entry Point

```toml
# pyproject.toml
[project.entry-points."amplifier.modules"]
loop-myloop = "amplifier_module_loop_myloop:mount"
```

---

## Configuration

### Mount Plan Configuration

```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "orchestrator_source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"
    },
    "orchestrator": {
        "config": {
            # Orchestrator-specific settings
            "max_iterations": 10,
            "timeout": 300,
            "buffer_size": 10  # loop-streaming specific
        }
    }
}
```

### Profile Configuration

```yaml
# profiles/prod.md
---
session:
  orchestrator: loop-events
  orchestrator_source: git+https://...

orchestrator:
  config:
    max_iterations: 20    # Conservative for production
    timeout: 300
    emit_events: true
---
```

### Common Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_iterations` | int | -1 | Maximum loop iterations (-1 = unlimited) |
| `timeout` | int | 300 | Timeout in seconds |

### Orchestrator-Specific Options

**loop-streaming:**
- `buffer_size`: Tokens to buffer before flushing (default: 10)

**loop-events:**
- `emit_events`: Enable event emission (default: true)

---

## Execution Flow

### Basic Execution (loop-basic)

```python
async def execute(self, prompt: str) -> str:
    # 1. Add user message
    await self.context.add_message({
        "role": "user",
        "content": prompt
    })

    iterations = 0
    max_iterations = self.config.get("max_iterations", -1)

    while True:
        # 2. Check iteration limit
        iterations += 1
        if max_iterations > 0 and iterations > max_iterations:
            raise RuntimeError("Max iterations exceeded")

        # 3. Get context messages
        messages = await self.context.get_messages()

        # 4. Call provider
        response = await self.provider.generate(messages)

        # 5. Add assistant message
        await self.context.add_message(response)

        # 6. Check for tool calls
        if not has_tool_calls(response):
            # Done! Return text response
            return extract_text(response)

        # 7. Execute tools (sequential)
        for tool_call in extract_tool_calls(response):
            result = await self.tools.execute(tool_call)

            # 8. Add tool result
            await self.context.add_message({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result
                }]
            })

        # Loop back to step 3
```

### Streaming Execution (loop-streaming)

```python
async def stream_execute(self, prompt: str) -> AsyncIterator[str]:
    # 1. Add user message
    await self.context.add_message({
        "role": "user",
        "content": prompt
    })

    while True:
        messages = await self.context.get_messages()

        # 2. Stream from provider
        collected_response = {"role": "assistant", "content": []}

        async for chunk in self.provider.stream_generate(messages):
            # 3. Yield tokens to user
            if chunk["type"] == "text":
                yield chunk["text"]
                collected_response["content"].append(chunk)

            elif chunk["type"] == "tool_use":
                # Collect tool call
                collected_response["content"].append(chunk)

        # 4. Add complete response to context
        await self.context.add_message(collected_response)

        # 5. Check for tool calls
        tool_calls = extract_tool_calls(collected_response)
        if not tool_calls:
            return  # Done

        # 6. Execute tools in PARALLEL
        tasks = [
            self.tools.execute(tc)
            for tc in tool_calls
        ]
        results = await asyncio.gather(*tasks)

        # 7. Add results in ORIGINAL ORDER (determinism)
        for tool_call, result in zip(tool_calls, results):
            await self.context.add_message({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result
                }]
            })

        # Loop back
```

### Event-Driven Execution (loop-events)

```python
async def execute(self, prompt: str) -> str:
    # Emit start event
    await self.hooks.emit("orchestrator:start", {"prompt": prompt})

    await self.context.add_message({
        "role": "user",
        "content": prompt
    })

    iteration = 0
    while True:
        iteration += 1

        # Emit iteration start
        await self.hooks.emit("orchestrator:iteration:start", {
            "iteration": iteration
        })

        messages = await self.context.get_messages()

        # Emit provider call
        await self.hooks.emit("orchestrator:provider:call", {
            "message_count": len(messages)
        })

        try:
            response = await self.provider.generate(messages)
        except Exception as e:
            # Emit error
            await self.hooks.emit("orchestrator:error", {
                "error": str(e),
                "iteration": iteration
            })
            raise

        # Emit provider response
        await self.hooks.emit("orchestrator:provider:response", {
            "has_tool_calls": has_tool_calls(response)
        })

        await self.context.add_message(response)

        if not has_tool_calls(response):
            await self.hooks.emit("orchestrator:complete", {
                "iterations": iteration
            })
            return extract_text(response)

        # Execute tools with events
        for tool_call in extract_tool_calls(response):
            await self.hooks.emit("orchestrator:tool:execute", {
                "tool": tool_call["name"]
            })

            result = await self.tools.execute(tool_call)

            await self.hooks.emit("orchestrator:tool:complete", {
                "tool": tool_call["name"]
            })

            await self.context.add_message({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result
                }]
            })
```

---

## Best Practices

### 1. Choose the Right Orchestrator

**For development/testing:**
```yaml
session:
  orchestrator: loop-basic  # Simple, deterministic, easy to debug
```

**For interactive applications:**
```yaml
session:
  orchestrator: loop-streaming  # Streaming, parallel tools, great UX
```

**For production:**
```yaml
session:
  orchestrator: loop-events  # Observability, monitoring, production-ready
```

### 2. Set Appropriate Iteration Limits

**Development (permissive):**
```yaml
orchestrator:
  config:
    max_iterations: -1  # Unlimited (trust the agent)
```

**Production (conservative):**
```yaml
orchestrator:
  config:
    max_iterations: 20  # Prevent runaway loops
```

**Why limit?** Prevents infinite loops from:
- Tool errors causing retries
- LLM getting stuck in reasoning loops
- Unexpected tool call patterns

### 3. Configure Timeouts

```yaml
orchestrator:
  config:
    timeout: 300  # 5 minutes default

# For long-running operations:
orchestrator:
  config:
    timeout: 1800  # 30 minutes
```

**Why timeout?** Prevents:
- Hung provider calls
- Infinite loops (when max_iterations = -1)
- Resource exhaustion

### 4. Parallel vs Sequential Tool Execution

**When to use parallel (loop-streaming):**
- ✅ Tools are independent (no shared state)
- ✅ Tools are I/O bound (network, file system)
- ✅ Speed matters (interactive use)

**Example:** Reading multiple files simultaneously
```
read_file(file1.txt) ─┐
read_file(file2.txt) ─┤ (parallel = fast)
read_file(file3.txt) ─┘
```

**When to use sequential (loop-basic):**
- ⚠️ Tools have dependencies (Tool B needs Tool A's result)
- ⚠️ Tools modify shared state (writes to same resource)
- ⚠️ Debugging (easier to follow execution)

**Example:** Sequential file operations
```
write_file(config.txt)
  → read_file(config.txt)  (depends on write)
    → edit_file(config.txt)  (depends on read)
```

### 5. Handle Streaming Gracefully

```python
# Good: Handle streaming properly
async for chunk in session.stream_execute(prompt):
    print(chunk, end="", flush=True)
print()  # Final newline

# Bad: Blocking on streaming
response = await session.execute(prompt)  # Waits for complete response
```

**Benefits of streaming:**
- Immediate user feedback (perceived performance)
- Can interrupt long responses (Ctrl+C)
- Better UX for long outputs

---

## Troubleshooting

### Issue: Infinite Loop

**Symptoms:**
- Session hangs indefinitely
- Max iterations exceeded error
- High API costs (many provider calls)

**Causes:**
1. Tool keeps failing, LLM retries
2. LLM stuck in reasoning loop
3. Tool result triggers more tool calls infinitely

**Solutions:**

1. **Set max_iterations:**
   ```yaml
   orchestrator:
     config:
       max_iterations: 10  # Stop after 10 iterations
   ```

2. **Debug with loop-basic:**
   ```yaml
   session:
     orchestrator: loop-basic  # Sequential, easier to debug
   ```

3. **Inspect tool results:**
   ```python
   # Add logging hook to see what's happening
   hooks:
     - module: hooks-logging
       config:
         level: DEBUG  # See all tool calls and results
   ```

---

### Issue: Slow Tool Execution

**Symptoms:**
- Long wait between prompt and response
- Tools taking too long

**Causes:**
1. Sequential tool execution (loop-basic)
2. Slow tools (network, file operations)
3. Many tool calls

**Solutions:**

1. **Switch to parallel execution:**
   ```yaml
   session:
     orchestrator: loop-streaming  # Parallel tools
   ```

2. **Optimize tools:**
   - Cache expensive operations
   - Reduce I/O
   - Parallelize within tools

3. **Reduce tool calls:**
   - Combine related operations
   - Add system instruction to minimize tool use

---

### Issue: Streaming Not Working

**Symptoms:**
- Response appears all at once (not token-by-token)
- Using loop-streaming but no streaming

**Causes:**
1. Using `session.execute()` instead of `session.stream_execute()`
2. Provider doesn't support streaming
3. Buffering in terminal/UI

**Solutions:**

1. **Use stream_execute:**
   ```python
   # Wrong
   response = await session.execute(prompt)

   # Right
   async for chunk in session.stream_execute(prompt):
       print(chunk, end="", flush=True)
   ```

2. **Check provider:**
   ```yaml
   providers:
     - module: provider-anthropic  # ✅ Supports streaming
     # - module: provider-mock  # ❌ May not support streaming
   ```

3. **Flush output:**
   ```python
   print(chunk, end="", flush=True)  # flush=True important!
   ```

---

### Issue: Events Not Firing

**Symptoms:**
- Using loop-events but hooks not called
- Logging hook shows no events

**Causes:**
1. Wrong orchestrator (loop-basic doesn't emit events)
2. Events disabled in config
3. No hooks mounted

**Solutions:**

1. **Verify orchestrator:**
   ```yaml
   session:
     orchestrator: loop-events  # Only this emits events
   ```

2. **Enable events:**
   ```yaml
   orchestrator:
     config:
       emit_events: true  # Default, but verify
   ```

3. **Mount hooks:**
   ```yaml
   hooks:
     - module: hooks-logging  # Required to receive events
   ```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| loop-basic | `amplifier-dev/amplifier-module-loop-basic/` |
| loop-streaming | `amplifier-dev/amplifier-module-loop-streaming/` |
| loop-events | `amplifier-dev/amplifier-module-loop-events/` |
| Orchestrator interface | `amplifier-core/amplifier_core/coordinator.py` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Iteration** | One pass through: prompt → LLM → tools → LLM |
| **Tool call** | LLM requesting to execute a tool |
| **Tool result** | Output from tool execution |
| **Streaming** | Token-by-token response delivery |
| **Parallel execution** | Multiple tools running concurrently |

### Related Guides

- [**Mount Plans Guide**](./mounts.md) - How orchestrators are loaded
- [**Context Guide**](./context.md) - How orchestrators use context
- [**Tools Guide**](./tools.md) - How orchestrators execute tools
- [**Development Guide**](./development.md) - Creating custom orchestrators

---

## Quick Reference

### Choosing an Orchestrator

```
Need streaming?
    ├─ Yes → loop-streaming or loop-events
    └─ No → loop-basic

Need parallel tools?
    ├─ Yes → loop-streaming or loop-events
    └─ No → loop-basic

Need observability?
    ├─ Yes → loop-events
    └─ No → loop-streaming or loop-basic

Development/testing?
    └─ loop-basic (simplest, most deterministic)

Interactive use?
    └─ loop-streaming (best UX)

Production?
    └─ loop-events (full observability)
```

### Configuration Template

```yaml
session:
  orchestrator: loop-streaming  # or loop-basic, loop-events
  orchestrator_source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main

orchestrator:
  config:
    max_iterations: 10      # Prevent infinite loops (-1 = unlimited)
    timeout: 300            # Timeout in seconds
    # loop-streaming specific:
    buffer_size: 10         # Token buffering
    # loop-events specific:
    emit_events: true       # Enable event emission
```

### Common Operations

```python
# Basic execution
response = await session.execute("Read /data/test.txt")

# Streaming execution
async for chunk in session.stream_execute("Write a long story"):
    print(chunk, end="", flush=True)

# Check iteration count (if exposed by orchestrator)
iterations = session.coordinator.orchestrator.iteration_count
```

---

**The orchestrator is the agent's execution engine. Choose based on your needs: simple for testing, streaming for UX, events for production.**
