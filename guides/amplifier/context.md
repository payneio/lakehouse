# Amplifier Context Managers Guide

**Comprehensive guide for understanding and working with Amplifier context managers**

---

## Table of Contents

1. [What Are Context Managers?](#what-are-context-managers)
2. [How Context Managers Work](#how-context-managers-work)
3. [Available Context Managers](#available-context-managers)
4. [Context Manager Contract](#context-manager-contract)
5. [Configuration](#configuration)
6. [Message Management](#message-management)
7. [Compaction Strategies](#compaction-strategies)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Context Managers?

A **Context Manager** is the component responsible for maintaining conversation state in an Amplifier session. It stores messages, manages memory limits, and provides compaction strategies when the conversation grows too large.

### Key Responsibilities

- **Message storage**: Keeping conversation history
- **Memory management**: Tracking token usage and limits
- **Compaction**: Reducing context size when limits approached
- **State integrity**: Preserving tool-use/tool-result pairs
- **Persistence** (some implementations): Saving state across sessions

### Philosophy

Context managers embody the "mechanism for memory" principle:
- **Kernel responsibility**: The context manager is part of the core loop
- **Session-scoped**: One context manager per session
- **Pluggable implementations**: Different strategies for different needs
- **Simple contract**: Add, get, compact - that's it

Think of it as: **The context manager is the session's memory.**

---

## How Context Managers Work

### The Lifecycle

```
┌─────────────────────┐
│  1. Session Starts  │  Context manager initialized
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Messages Added  │  User and assistant messages stored
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Token Tracking  │  Count tokens in conversation
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Limit Check     │  Compare usage to max_tokens
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Compaction?     │  If near limit, compact
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  6. Continue        │  Loop back to step 2
└─────────────────────┘
```

### Integration with Session

```python
from amplifier_core import AmplifierSession

# Context manager specified in mount plan
mount_plan = {
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple",  # ← Context manager
        "context_source": "git+https://..."
    }
}

async with AmplifierSession(config=mount_plan) as session:
    # Context manager automatically:
    # - Stores user message
    # - Stores assistant response
    # - Tracks tokens
    # - Compacts if needed
    response = await session.execute("Hello!")
```

---

## Available Context Managers

### context-simple

**In-memory message list with automatic compaction.**

**Best for:**
- Development and testing
- Short conversations (< 100 messages)
- Stateless applications
- Quick prototypes

**Configuration:**
```yaml
session:
  context: context-simple
  context_source: git+https://github.com/microsoft/amplifier-module-context-simple@main

context:
  config:
    max_tokens: 200000           # Token limit (default)
    compact_threshold: 0.92      # Compact at 92% usage
    auto_compact: true           # Enable automatic compaction
```

**Compaction strategy:**
- Keeps: System messages + last 10 conversation messages
- Preserves: Tool-use/tool-result pairs atomically
- Deduplicates: Non-tool messages (by role + content prefix)

**Characteristics:**
- ✅ Simple and predictable
- ✅ No external dependencies
- ✅ Fast in-memory operations
- ❌ No persistence (session ends, context lost)
- ❌ Fixed compaction strategy

---

### context-persistent

**File-based persistent context with customizable compaction.**

**Best for:**
- Production applications
- Long-running conversations
- Multi-session continuity
- Custom compaction needs

**Configuration:**
```yaml
session:
  context: context-persistent
  context_source: git+https://github.com/microsoft/amplifier-module-context-persistent@main

context:
  config:
    max_tokens: 200000
    compact_threshold: 0.95      # More aggressive threshold
    auto_compact: true
    storage_path: .amplifier/context  # Persistence location
    compaction_strategy: smart   # or "simple", "custom"
```

**Compaction strategies:**
- `simple`: Like context-simple (system + last 10)
- `smart`: Semantic importance + recency
- `custom`: User-defined strategy function

**Characteristics:**
- ✅ Survives session restarts
- ✅ Customizable compaction
- ✅ Exportable context
- ⚠️ Requires file system access
- ⚠️ Slightly slower than in-memory

---

### Comparison Matrix

| Feature | context-simple | context-persistent |
|---------|---------------|-------------------|
| **Storage** | In-memory | File-based |
| **Persistence** | No | Yes |
| **Speed** | Fastest | Fast |
| **Compaction** | Fixed | Customizable |
| **Dependencies** | None | File system |
| **Best for** | Dev/testing | Production |
| **Session continuity** | No | Yes |

---

## Context Manager Contract

### Mount Function

Every context manager must implement:

```python
async def mount(coordinator, config: dict):
    """
    Mount the context manager.

    Args:
        coordinator: The session coordinator
        config: Configuration from mount plan

    Returns:
        Optional cleanup function
    """
    manager = MyContextManager(config)
    coordinator.context = manager

    # Optional: return cleanup function
    async def cleanup():
        await manager.close()

    return cleanup
```

### Required Methods

```python
class ContextManager:
    async def add_message(self, message: dict):
        """Add a message to context."""
        pass

    async def get_messages(self) -> list[dict]:
        """Get all messages for LLM."""
        pass

    async def get_token_count(self) -> int:
        """Get current token usage."""
        pass

    async def compact(self) -> int:
        """
        Compact context, return tokens saved.

        Must preserve:
        - System messages
        - Tool-use/tool-result pairs (atomic)
        - Recent conversation flow
        """
        pass
```

### Entry Point

```toml
# pyproject.toml
[project.entry-points."amplifier.modules"]
context-mycontext = "amplifier_module_context_mycontext:mount"
```

---

## Configuration

### Mount Plan Configuration

```python
{
    "session": {
        "context": "context-simple",
        "context_source": "git+https://github.com/microsoft/amplifier-module-context-simple@main"
    },
    "context": {
        "config": {
            # Context-specific settings
            "max_tokens": 200000,
            "compact_threshold": 0.92,
            "auto_compact": true
        }
    }
}
```

### Profile Configuration

```yaml
# profiles/dev.md
---
session:
  context: context-persistent
  context_source: git+https://...

context:
  config:
    max_tokens: 200000
    compact_threshold: 0.95
    storage_path: .amplifier/context
---
```

### Common Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_tokens` | int | 200000 | Maximum tokens before compaction required |
| `compact_threshold` | float | 0.92 | Usage fraction triggering compaction (0.92 = 92%) |
| `auto_compact` | bool | true | Enable automatic compaction |

### Context-Specific Options

**context-simple:**
- No additional options

**context-persistent:**
- `storage_path`: Directory for persistence files
- `compaction_strategy`: "simple", "smart", or "custom"
- `export_on_compact`: Save pre-compaction snapshot

---

## Message Management

### Message Structure

Messages follow the Anthropic API format:

```python
{
    "role": "user",  # or "assistant"
    "content": [
        {
            "type": "text",
            "text": "Hello!"
        }
    ]
}
```

### Tool Messages

Tool-use and tool-result messages form **atomic pairs**:

```python
# Assistant with tool call
{
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_01A",
            "name": "read_file",
            "input": {"file_path": "/data/test.txt"}
        }
    ]
}

# MUST be followed by tool result
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01A",
            "content": "File contents here"
        }
    ]
}
```

**Critical invariant**: Every `tool_use` MUST have a matching `tool_result` in the next message. Context managers MUST preserve these pairs atomically during compaction.

### Adding Messages

```python
# Context manager handles automatically
async with AmplifierSession(config=mount_plan) as session:
    response = await session.execute("Hello!")
    # Context now contains:
    # 1. User message: "Hello!"
    # 2. Assistant response: "Hi there!"
```

### Retrieving Messages

```python
messages = await session.coordinator.context.get_messages()

for msg in messages:
    print(f"{msg['role']}: {msg['content']}")
```

---

## Compaction Strategies

### Why Compaction?

LLM API calls have token limits (typically 200k). Long conversations exceed limits. Compaction selectively removes messages to stay under limits while preserving:

1. **System instructions** (always kept)
2. **Recent messages** (working memory)
3. **Tool pairs** (data integrity)

### Simple Compaction (context-simple)

**Algorithm:**
```
1. Keep all system messages (role="system")
2. Keep last 10 conversation messages (user/assistant)
3. Preserve tool-use/tool-result pairs atomically
4. Deduplicate identical non-tool messages
```

**Example:**
```
Before (100 messages, 190k tokens):
- system (2 messages)
- user/assistant conversation (98 messages)

After (12 messages, 50k tokens):
- system (2 messages)
- user/assistant (last 10 messages)
```

**Strengths:**
- Predictable and deterministic
- Fast (no LLM calls)
- Preserves recent context

**Weaknesses:**
- Loses middle conversation
- No semantic understanding
- Fixed retention count

---

### Smart Compaction (context-persistent)

**Algorithm:**
```
1. Keep all system messages
2. Score messages by:
   - Recency (newer = higher)
   - Semantic importance (LLM judges)
   - Tool relationship (pairs inseparable)
3. Keep top-scoring messages within token budget
```

**Example:**
```
Before (100 messages, 190k tokens):
- Important decision at message 20
- Long tangent at messages 30-60
- Recent work at messages 90-100

After (30 messages, 80k tokens):
- system messages
- Message 20 (high importance score)
- Messages 90-100 (recency + importance)
- (Tangent removed as low-importance)
```

**Strengths:**
- Preserves important context
- Semantic understanding
- Adaptive to conversation

**Weaknesses:**
- Slower (requires LLM call)
- Non-deterministic
- More complex

---

### Tool Pair Preservation

**Critical implementation detail**: Context managers MUST preserve tool-use/tool-result pairs atomically.

**Why:**
- Anthropic API validates: every `tool_use` must have matching `tool_result`
- Breaking pairs causes API errors
- Multiple tool_use in one message = multiple consecutive tool_result messages

**Implementation pattern:**

```python
def preserve_tool_pairs(messages):
    """
    When keeping a message, check if it's part of a tool pair.
    If so, keep the pair atomically.
    """
    kept = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        # If assistant message with tool_use
        if msg["role"] == "assistant" and has_tool_use(msg):
            # Must keep next message(s) with tool_result(s)
            kept.append(msg)
            i += 1
            # Keep consecutive tool result messages
            while i < len(messages) and has_tool_result(messages[i]):
                kept.append(messages[i])
                i += 1
        # If tool result, must keep previous assistant
        elif has_tool_result(msg):
            # Walk back to find assistant with tool_use
            # Keep entire group atomically
            pass
        else:
            # Normal message, can keep/discard independently
            kept.append(msg)
            i += 1

    return kept
```

---

## Best Practices

### 1. Choose the Right Context Manager

**For development/testing:**
```yaml
session:
  context: context-simple  # Fast, simple, no persistence needed
```

**For production:**
```yaml
session:
  context: context-persistent  # Survives restarts, customizable

context:
  config:
    storage_path: /var/lib/amplifier/context
    compaction_strategy: smart
```

### 2. Set Appropriate Thresholds

**Conservative (early compaction):**
```yaml
context:
  config:
    max_tokens: 200000
    compact_threshold: 0.85  # Compact at 85% (170k tokens)
```

**Aggressive (late compaction):**
```yaml
context:
  config:
    max_tokens: 200000
    compact_threshold: 0.95  # Compact at 95% (190k tokens)
```

**Trade-off**: Early = more compactions, better safety margin. Late = fewer compactions, more context retained.

### 3. Monitor Token Usage

```python
# Check current usage
token_count = await session.coordinator.context.get_token_count()
max_tokens = session.coordinator.context.config.get("max_tokens", 200000)

usage_percent = (token_count / max_tokens) * 100
print(f"Context usage: {usage_percent:.1f}%")

if usage_percent > 90:
    print("Warning: Approaching token limit")
```

### 4. Handle Compaction Events

```python
# Hook into compaction events (if supported)
@session.coordinator.hooks.on("context:compact")
async def on_compact(event):
    print(f"Context compacted: {event['tokens_before']} → {event['tokens_after']}")
    print(f"Saved: {event['tokens_saved']} tokens")
```

### 5. Test Compaction Behavior

```python
# Simulate long conversation
for i in range(100):
    await session.execute(f"Message {i}")

# Check that context was compacted
messages = await session.coordinator.context.get_messages()
assert len(messages) < 100  # Compaction occurred
```

---

## Troubleshooting

### Issue: Context Growing Too Large

**Symptoms:**
- Slow LLM responses (large context)
- High API costs (token usage)
- Eventually: API errors (context limit exceeded)

**Solutions:**

1. **Lower compact_threshold:**
   ```yaml
   context:
     config:
       compact_threshold: 0.85  # More aggressive compaction
   ```

2. **Reduce max_tokens:**
   ```yaml
   context:
     config:
       max_tokens: 100000  # Smaller limit forces earlier compaction
   ```

3. **Manual compaction:**
   ```python
   # Force compaction now
   tokens_saved = await session.coordinator.context.compact()
   print(f"Saved {tokens_saved} tokens")
   ```

---

### Issue: Important Context Lost

**Symptoms:**
- Agent "forgets" earlier decisions
- Repeats questions
- Loses track of conversation

**Solutions:**

1. **Use context-persistent with smart compaction:**
   ```yaml
   session:
     context: context-persistent

   context:
     config:
       compaction_strategy: smart  # Semantic importance scoring
   ```

2. **Increase retention in simple compaction:**
   - Contribute a configurable retention count to context-simple
   - Fork and modify compaction logic

3. **Use system messages for critical info:**
   ```python
   # Add important context to system message
   await session.coordinator.context.add_message({
       "role": "system",
       "content": "IMPORTANT: User decided to use PostgreSQL"
   })
   # System messages never compacted
   ```

---

### Issue: Tool Pair Errors

**Error:** `"tool_use_id 'toolu_xyz' not found"`

**Cause:** Compaction broke tool-use/tool-result pair

**Solution:**
- This is a bug in the context manager
- All context managers MUST preserve tool pairs atomically
- Report the issue with reproduction steps

**Verification:**
```python
messages = await session.coordinator.context.get_messages()

# Verify all tool_use have matching tool_result
for i, msg in enumerate(messages):
    if has_tool_use(msg):
        next_msg = messages[i + 1]
        assert has_tool_result(next_msg), "Broken tool pair!"
```

---

### Issue: Context Not Persisting

**Symptoms:**
- Session restarts, context lost
- Using context-persistent but acts like context-simple

**Solutions:**

1. **Check storage_path exists:**
   ```bash
   ls -la .amplifier/context/
   # Should show session files
   ```

2. **Verify configuration:**
   ```yaml
   session:
     context: context-persistent  # Not context-simple!

   context:
     config:
       storage_path: .amplifier/context  # Absolute or relative path
   ```

3. **Check file permissions:**
   ```bash
   # Ensure write access
   touch .amplifier/context/test.txt
   rm .amplifier/context/test.txt
   ```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| context-simple | `amplifier-dev/amplifier-module-context-simple/` |
| context-persistent | `amplifier-dev/amplifier-module-context-persistent/` |
| Context interface | `amplifier-core/amplifier_core/coordinator.py` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Message** | Single conversation turn (user or assistant) |
| **Token** | Unit of text (typically ~4 characters) |
| **Compaction** | Reducing context size while preserving important messages |
| **Tool pair** | Atomic unit: tool_use + tool_result |
| **System message** | Special message type (never compacted) |

### Related Guides

- [**Mount Plans Guide**](./mounts.md) - How context managers are loaded
- [**Orchestrators Guide**](./orchestrators.md) - How orchestrators use context
- [**Development Guide**](./development.md) - Creating custom context managers

---

## Quick Reference

### Choosing a Context Manager

```
Need persistence?
    ├─ Yes → context-persistent
    └─ No → context-simple

Need custom compaction?
    ├─ Yes → context-persistent (with strategy)
    └─ No → context-simple (fixed strategy)

Development/testing?
    └─ context-simple (fastest, simplest)
```

### Configuration Template

```yaml
session:
  context: context-simple  # or context-persistent
  context_source: git+https://github.com/microsoft/amplifier-module-context-simple@main

context:
  config:
    max_tokens: 200000           # Token limit
    compact_threshold: 0.92      # Compact at 92%
    auto_compact: true           # Enable auto-compaction
    # context-persistent only:
    storage_path: .amplifier/context
    compaction_strategy: smart   # simple|smart|custom
```

### Common Operations

```python
# Get current context
messages = await session.coordinator.context.get_messages()

# Check token usage
tokens = await session.coordinator.context.get_token_count()

# Force compaction
tokens_saved = await session.coordinator.context.compact()

# Add system message (never compacted)
await session.coordinator.context.add_message({
    "role": "system",
    "content": "Important persistent context"
})
```

---

**The context manager is the session's memory. Choose wisely, configure appropriately, and trust the compaction strategy.**
