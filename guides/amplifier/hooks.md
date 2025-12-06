# Amplifier Hooks Guide

**Comprehensive guide for understanding and working with Amplifier hooks**

---

## Table of Contents

1. [What Are Hooks?](#what-are-hooks)
2. [How Hooks Work](#how-hooks-work)
3. [Available Hooks](#available-hooks)
4. [Hook Contract](#hook-contract)
5. [Configuration](#configuration)
6. [Event System](#event-system)
7. [Best Practices](#best-practices)
8. [Creating Custom Hooks](#creating-custom-hooks)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Hooks?

**Hooks** are observability and extension points in the Amplifier execution flow. They allow you to observe, log, modify, or extend agent behavior without changing core code.

### Key Characteristics

- **Event-driven**: React to lifecycle events
- **Non-intrusive**: Don't modify core logic
- **Composable**: Multiple hooks work together
- **Observable**: Full visibility into execution
- **Extensible**: Add custom behavior

### Philosophy

Hooks embody the "observability mechanism" principle:
- **Mechanism for observation**: Hooks are how you see what's happening
- **Kernel emits events**: Core components fire lifecycle events
- **Hooks react**: Registered hooks respond to events
- **No core changes**: Observability without code modification

Think of it as: **Hooks are the agent's nervous system - sensing and responding to execution.**

---

## How Hooks Work

### The Lifecycle

```
┌─────────────────────┐
│  1. Hook Mounted    │  Module registers event handlers
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Event Emitted   │  Core component fires event
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Hook Receives   │  All registered handlers called
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Hook Reacts     │  Handler executes (log, modify, etc.)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Continue        │  Execution continues
└─────────────────────┘
```

### Integration with Session

```python
# Hooks mounted automatically from mount plan
mount_plan = {
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple"
    },
    "hooks": [
        {
            "module": "hooks-logging",
            "source": "git+https://...",
            "config": {
                "level": "INFO",
                "output": "console"
            }
        },
        {
            "module": "hooks-backup",
            "source": "git+https://..."
        }
    ]
}

async with AmplifierSession(config=mount_plan) as session:
    # Hooks automatically observe execution
    response = await session.execute("Read test.txt")

    # Behind the scenes, hooks received:
    # - session:start
    # - tool:invoked (read_file)
    # - tool:completed
    # - session:end
```

---

## Available Hooks

### hooks-logging

**Visibility into agent execution through lifecycle event logging.**

**Purpose:** Log all execution events for debugging and monitoring

**Events logged:**
- Session lifecycle (start, end)
- Tool invocations and results
- Sub-agent spawning and completion
- Errors and warnings
- LLM request/response (when debug enabled)

**Configuration:**
```yaml
hooks:
  - module: hooks-logging
    source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
    config:
      level: "INFO"            # DEBUG, INFO, WARNING, ERROR
      output: "console"        # console, file, or both
      file: "amplifier.log"    # If output includes "file"
      auto_discover: true      # Auto-discover module events
      additional_events: []    # Manual event additions
```

**Log levels:**
- `DEBUG`: Everything including LLM request/response details
- `INFO`: Key events (tool calls, agent activity) - recommended
- `WARNING`: Warnings and errors only
- `ERROR`: Errors only

**Example output:**
```
2025-10-06 12:00:00 [INFO] === Session Started ===
2025-10-06 12:00:01 [INFO] Tool invoked: read_file
2025-10-06 12:00:02 [INFO] Tool completed: read_file ✓
2025-10-06 12:00:03 [INFO] === Session Ended ===
```

---

### hooks-backup

**Automatic conversation backup and recovery.**

**Purpose:** Save conversation state periodically for recovery

**Features:**
- Automatic periodic backups
- Save on session end
- Restore from backup on crash
- Configurable backup interval

**Configuration:**
```yaml
hooks:
  - module: hooks-backup
    source: git+https://github.com/microsoft/amplifier-module-hooks-backup@main
    config:
      backup_dir: .amplifier/backups
      interval: 300              # Backup every 5 minutes
      max_backups: 10            # Keep last 10 backups
      backup_on_end: true        # Save when session ends
```

**Backup format:**
- JSON files with timestamp
- Contains full context + metadata
- Portable (can restore anywhere)

---

### hooks-approval

**Human approval for high-risk operations.**

**Purpose:** Require human review before executing dangerous actions

**Features:**
- Pause execution for approval
- Show tool details to user
- Accept/reject decision
- Timeout handling

**Configuration:**
```yaml
hooks:
  - module: hooks-approval
    source: git+https://github.com/microsoft/amplifier-module-hooks-approval@main
    config:
      auto_approve: false        # Manual approval required
      timeout: 300               # Wait up to 5 minutes
      approval_method: "cli"     # cli, web, or custom
```

**Used with tools:**
```yaml
tools:
  - module: tool-bash
    config:
      require_approval: true     # Trigger approval hook
```

**Flow:**
```
1. LLM requests: execute_bash("rm important.txt")
2. Hook intercepts: "Approve deletion of important.txt? [y/n]"
3. Human responds: "n"
4. Hook rejects: Tool execution aborted
5. LLM receives: "User rejected operation"
```

---

### hooks-redaction

**Automatic redaction of sensitive information in logs.**

**Purpose:** Remove secrets from logs before they're written

**Features:**
- Pattern-based redaction (regex)
- Common secret patterns (API keys, passwords)
- Custom redaction rules
- Preserves log structure

**Configuration:**
```yaml
hooks:
  - module: hooks-redaction
    source: git+https://github.com/microsoft/amplifier-module-hooks-redaction@main
    config:
      enabled: true
      patterns:
        - '(sk-[a-zA-Z0-9]{48})'       # API keys
        - '(password["\']:\s*["\'][^"\']+["\'])'  # Passwords
      replacement: "[REDACTED]"
```

**Example:**
```
Before: "Using API key sk-ant-abc123..."
After:  "Using API key [REDACTED]"
```

---

### hooks-scheduler-cost-aware

**Cost-based provider selection and routing.**

**Purpose:** Route requests to cheaper providers when appropriate

**Features:**
- Cost tracking per provider
- Budget limits
- Automatic provider switching
- Cost reporting

**Configuration:**
```yaml
hooks:
  - module: hooks-scheduler-cost-aware
    source: git+https://github.com/microsoft/amplifier-module-hooks-scheduler-cost-aware@main
    config:
      daily_budget: 10.00        # USD per day
      cost_per_token:
        provider-anthropic: 0.000015   # $0.015 per 1k tokens
        provider-openai: 0.000002      # $0.002 per 1k tokens
      prefer_cheaper: true       # Use cheaper when possible
```

**Behavior:**
- Tracks token usage and costs
- Warns when approaching budget
- Can auto-switch to cheaper provider
- Blocks when budget exceeded

---

### hooks-scheduler-heuristic

**Intelligent provider selection based on task characteristics.**

**Purpose:** Route different tasks to appropriate providers

**Features:**
- Task classification (coding, writing, analysis)
- Provider capabilities matching
- Performance optimization
- Automatic routing

**Configuration:**
```yaml
hooks:
  - module: hooks-scheduler-heuristic
    source: git+https://github.com/microsoft/amplifier-module-hooks-scheduler-heuristic@main
    config:
      rules:
        - task_type: "code"
          preferred_provider: "provider-anthropic"
          preferred_model: "claude-sonnet-4-5"
        - task_type: "creative"
          preferred_provider: "provider-openai"
          preferred_model: "gpt-4"
```

**Task detection:**
- Analyzes prompt content
- Classifies task type
- Selects optimal provider
- Falls back if unavailable

---

### hooks-status-context

**Context usage monitoring and alerts.**

**Purpose:** Track context growth and warn before limits

**Features:**
- Real-time token tracking
- Usage percentage calculation
- Threshold warnings
- Compaction suggestions

**Configuration:**
```yaml
hooks:
  - module: hooks-status-context
    source: git+https://github.com/microsoft/amplifier-module-hooks-status-context@main
    config:
      warn_threshold: 0.80       # Warn at 80%
      alert_threshold: 0.90      # Alert at 90%
      display_interval: 10       # Update every 10 messages
```

**Output:**
```
[80%] Context usage: 160k/200k tokens (warning threshold)
[90%] Context usage: 180k/200k tokens (alert! compaction recommended)
```

---

### hooks-streaming-ui

**Enhanced UI for streaming responses.**

**Purpose:** Improve display of streaming LLM responses

**Features:**
- Markdown rendering
- Syntax highlighting for code blocks
- Progress indicators
- Token count display

**Configuration:**
```yaml
hooks:
  - module: hooks-streaming-ui
    source: git+https://github.com/microsoft/amplifier-module-hooks-streaming-ui@main
    config:
      render_markdown: true      # Render markdown as formatted
      highlight_code: true       # Syntax highlight code blocks
      show_tokens: true          # Display token count
      theme: "dark"              # UI theme
```

---

### hooks-todo-reminder

**Automatic todo management and reminders.**

**Purpose:** Ensure agent maintains and completes todo lists

**Features:**
- Detect when todos should be used
- Remind to update todos
- Warn about stale todos
- Track completion

**Configuration:**
```yaml
hooks:
  - module: hooks-todo-reminder
    source: git+https://github.com/microsoft/amplifier-module-hooks-todo-reminder@main
    config:
      remind_interval: 5         # Remind every 5 messages
      warn_stale_after: 20       # Warn if todo unchanged for 20 messages
      suggest_threshold: 3       # Suggest todos for 3+ steps
```

**Behavior:**
```
User: "Implement authentication, add tests, and deploy"
Hook: [Suggestion] This task has multiple steps. Consider using todo list.

User: "What's the status?"
Hook: [Reminder] 3 todos pending: [authentication, tests, deploy]
```

---

### Comparison Matrix

| Hook | Category | Purpose | When to Use |
|------|----------|---------|-------------|
| **hooks-logging** | Observability | Log everything | Always (debugging, monitoring) |
| **hooks-backup** | Safety | Save state | Production (recovery) |
| **hooks-approval** | Safety | Human review | High-risk operations |
| **hooks-redaction** | Security | Hide secrets | Production (compliance) |
| **hooks-scheduler-cost-aware** | Optimization | Cost control | Budget-constrained |
| **hooks-scheduler-heuristic** | Optimization | Smart routing | Multi-provider setups |
| **hooks-status-context** | Monitoring | Track usage | Long conversations |
| **hooks-streaming-ui** | UX | Better display | Interactive CLI/web |
| **hooks-todo-reminder** | Productivity | Task tracking | Complex multi-step tasks |

---

## Hook Contract

### Mount Function

Every hook module must implement:

```python
async def mount(coordinator, config: dict):
    """
    Mount hook handlers.

    Args:
        coordinator: The session coordinator
        config: Configuration from mount plan

    Returns:
        Optional cleanup function
    """
    # Register event handlers
    @coordinator.hooks.on("tool:invoked")
    async def on_tool_invoked(event):
        print(f"Tool called: {event['tool_name']}")

    @coordinator.hooks.on("tool:completed")
    async def on_tool_completed(event):
        print(f"Tool finished: {event['tool_name']}")

    # Optional: return cleanup function
    async def cleanup():
        # Unregister handlers, close resources
        pass

    return cleanup
```

### Event Handler

```python
async def event_handler(event: dict):
    """
    Handle an event.

    Args:
        event: Event data dictionary containing:
            - event_type: str (event name)
            - timestamp: float (event time)
            - ... event-specific fields

    Can:
        - Log event
        - Modify event data (some events)
        - Abort operation (approval hooks)
        - Emit new events
    """
    # Extract event data
    tool_name = event.get("tool_name")

    # React to event
    logger.info(f"Tool {tool_name} was called")

    # Some events support modification
    if "modifiable" in event:
        event["modified_field"] = "new_value"
```

### Entry Point

```toml
# pyproject.toml
[project.entry-points."amplifier.modules"]
hooks-myhook = "amplifier_module_hooks_myhook:mount"
```

---

## Configuration

### Mount Plan Configuration

```python
{
    "hooks": [
        {
            "module": "hooks-logging",
            "source": "git+https://github.com/microsoft/amplifier-module-hooks-logging@main",
            "config": {
                "level": "INFO",
                "output": "console"
            }
        },
        {
            "module": "hooks-backup",
            "source": "git+https://github.com/microsoft/amplifier-module-hooks-backup@main",
            "config": {
                "backup_dir": ".amplifier/backups",
                "interval": 300
            }
        }
    ]
}
```

### Profile Configuration

```yaml
# profiles/prod.md
---
hooks:
  - module: hooks-logging
    source: git+https://...
    config:
      level: "WARNING"       # Production: only warnings/errors
      output: "file"
      file: "/var/log/amplifier/session.log"

  - module: hooks-backup
    source: git+https://...
    config:
      backup_dir: /var/lib/amplifier/backups
      interval: 300
      max_backups: 50

  - module: hooks-redaction
    source: git+https://...
    config:
      enabled: true          # Always redact in prod
---
```

---

## Event System

### Standard Events

**Session lifecycle:**
- `session:start` - Session begins
- `session:end` - Session ends
- `session:error` - Session error

**Tool execution:**
- `tool:invoked` - Tool called by LLM
- `tool:completed` - Tool finished successfully
- `tool:error` - Tool execution failed
- `tool:approval:requested` - Approval needed
- `tool:approval:granted` - Human approved
- `tool:approval:rejected` - Human rejected

**Sub-agent activity:**
- `agent:spawned` - Child agent started
- `agent:completed` - Child agent finished
- `agent:error` - Child agent failed

**Context management:**
- `context:compact:start` - Compaction beginning
- `context:compact:end` - Compaction finished
- `context:usage:warning` - Usage threshold crossed

**LLM provider:**
- `llm:request:debug` - LLM request details (DEBUG level)
- `llm:response:debug` - LLM response details (DEBUG level)
- `llm:request:raw` - Raw request (requires `raw_debug: true`)
- `llm:response:raw` - Raw response (requires `raw_debug: true`)

### Module-Declared Events

Modules can declare custom events via capabilities:

```python
# In module's mount()
async def mount(coordinator, config):
    # Declare observable events (aggregation pattern)
    obs_events = coordinator.get_capability("observability.events") or []
    obs_events.extend([
        "mymodule:started",
        "mymodule:progress",
        "mymodule:completed"
    ])
    coordinator.register_capability("observability.events", obs_events)

    # Emit events at appropriate times
    await coordinator.hooks.emit("mymodule:started", {"config": config})
    # ... module work
    await coordinator.hooks.emit("mymodule:completed", {"status": "success"})
```

### Auto-Discovery

Hooks like `hooks-logging` automatically discover and handle module events:

```python
# hooks-logging automatically:
# 1. Queries coordinator.get_capability("observability.events")
# 2. Registers handlers for all discovered events
# 3. Logs events alongside standard events

# Result: Custom module events appear in logs automatically!
```

### Event Data Structure

```python
{
    "event_type": "tool:invoked",   # Event name
    "timestamp": 1696500000.123,    # Unix timestamp
    "session_id": "abc123",         # Session identifier

    # Event-specific fields
    "tool_name": "read_file",
    "tool_params": {
        "file_path": "/data/test.txt"
    }
}
```

---

## Best Practices

### 1. Always Enable Logging

**Development:**
```yaml
hooks:
  - module: hooks-logging
    config:
      level: "DEBUG"         # See everything
      output: "console"
```

**Production:**
```yaml
hooks:
  - module: hooks-logging
    config:
      level: "WARNING"       # Only important events
      output: "file"
      file: "/var/log/amplifier/session.log"
```

### 2. Layer Hooks for Defense in Depth

```yaml
hooks:
  - module: hooks-logging       # Observability
  - module: hooks-backup        # Recovery
  - module: hooks-redaction     # Security
  - module: hooks-approval      # Safety
```

**Each hook adds a layer:**
- Logging: Know what happened
- Backup: Recover from failures
- Redaction: Protect secrets
- Approval: Prevent mistakes

### 3. Use Auto-Discovery for Module Events

**Good: Auto-discovery (zero configuration)**
```yaml
hooks:
  - module: hooks-logging
    config:
      auto_discover: true    # Default: discovers module events automatically
```

**Only disable for precise control:**
```yaml
hooks:
  - module: hooks-logging
    config:
      auto_discover: false   # Disable discovery
      additional_events:     # Manually specify
        - "specific:event:only"
```

### 4. Configure Appropriate Log Levels

**By environment:**
```yaml
# Development
hooks:
  - module: hooks-logging
    config:
      level: "DEBUG"         # See everything

# Staging
hooks:
  - module: hooks-logging
    config:
      level: "INFO"          # Key events only

# Production
hooks:
  - module: hooks-logging
    config:
      level: "WARNING"       # Problems only
```

### 5. Monitor Context Usage

```yaml
hooks:
  - module: hooks-status-context
    config:
      warn_threshold: 0.80   # Early warning
      alert_threshold: 0.90  # Urgent alert
```

**Prevents:**
- Unexpected compaction
- Context loss
- API errors from exceeding limits

---

## Creating Custom Hooks

### Step 1: Define Event Handlers

```python
# amplifier_module_hooks_myhook/__init__.py

async def mount(coordinator, config):
    """Mount custom hook."""

    # Extract config
    threshold = config.get("threshold", 100)

    # Register handler for standard event
    @coordinator.hooks.on("tool:invoked")
    async def on_tool_invoked(event):
        tool_name = event["tool_name"]
        print(f"Tool called: {tool_name}")

    # Register handler for custom event
    @coordinator.hooks.on("mymodule:custom")
    async def on_custom(event):
        value = event.get("value", 0)
        if value > threshold:
            print(f"Warning: value {value} exceeds threshold {threshold}")
```

### Step 2: Declare Observable Events (Optional)

```python
async def mount(coordinator, config):
    # If your module emits events, declare them
    obs_events = coordinator.get_capability("observability.events") or []
    obs_events.extend([
        "myhook:started",
        "myhook:warning"
    ])
    coordinator.register_capability("observability.events", obs_events)

    # Then emit them
    await coordinator.hooks.emit("myhook:started", {})
```

### Step 3: Add Configuration

```python
async def mount(coordinator, config):
    # Extract config with defaults
    enabled = config.get("enabled", True)
    output_file = config.get("output_file", None)

    if not enabled:
        return  # Skip mounting

    # Use config in handlers
    @coordinator.hooks.on("tool:invoked")
    async def on_tool_invoked(event):
        if output_file:
            with open(output_file, "a") as f:
                f.write(f"Tool: {event['tool_name']}\n")
```

### Step 4: Package as Module

```toml
# pyproject.toml
[project]
name = "amplifier-module-hooks-myhook"
version = "1.0.0"

dependencies = [
    "amplifier-core>=1.0.0"
]

[project.entry-points."amplifier.modules"]
hooks-myhook = "amplifier_module_hooks_myhook:mount"
```

### Step 5: Use in Profile

```yaml
hooks:
  - module: hooks-myhook
    source: git+https://github.com/org/amplifier-module-hooks-myhook@main
    config:
      enabled: true
      threshold: 100
      output_file: /var/log/myhook.log
```

---

## Troubleshooting

### Issue: Events Not Being Logged

**Symptoms:**
- hooks-logging mounted but no output
- Events not appearing in logs

**Causes:**
1. Wrong log level (events below threshold)
2. Orchestrator not emitting events (loop-basic, loop-streaming)
3. Hook not mounted

**Solutions:**

1. **Lower log level:**
   ```yaml
   hooks:
     - module: hooks-logging
       config:
         level: "DEBUG"  # See all events
   ```

2. **Use event-emitting orchestrator:**
   ```yaml
   session:
     orchestrator: loop-events  # Only this emits full events
   ```

3. **Verify hook mounted:**
   ```bash
   # Check session logs for hook mount confirmation
   ```

---

### Issue: Too Much Log Volume

**Symptoms:**
- Huge log files
- Slow performance
- Storage filling up

**Causes:**
1. DEBUG level in production
2. Raw debug enabled (`raw_debug: true`)
3. Long conversations without log rotation

**Solutions:**

1. **Adjust log level:**
   ```yaml
   hooks:
     - module: hooks-logging
       config:
         level: "WARNING"  # Production: only problems
   ```

2. **Disable raw debug:**
   ```yaml
   providers:
     - module: provider-anthropic
       config:
         debug: true       # Standard debug OK
         raw_debug: false  # Disable ultra-verbose
   ```

3. **Enable log rotation:**
   ```yaml
   hooks:
     - module: hooks-logging
       config:
         output: "file"
         file: "/var/log/amplifier.log"
         max_size: 10485760  # 10MB
         backup_count: 5     # Keep 5 old files
   ```

---

### Issue: Approval Hook Timing Out

**Symptoms:**
- "Approval timeout" errors
- Operations aborted

**Causes:**
1. Timeout too short
2. User AFK
3. Approval UI not responding

**Solutions:**

1. **Increase timeout:**
   ```yaml
   hooks:
     - module: hooks-approval
       config:
         timeout: 600  # 10 minutes
   ```

2. **Use auto-approve for dev:**
   ```yaml
   hooks:
     - module: hooks-approval
       config:
         auto_approve: true  # Dev only!
   ```

3. **Check approval UI:**
   - Verify CLI is responsive
   - Check web UI connectivity
   - Test approval mechanism

---

### Issue: Hook Order Matters

**Symptoms:**
- Hooks not seeing each other's effects
- Events processed in wrong order

**Causes:**
1. Hook order in mount plan affects execution order
2. Some hooks modify events
3. Race conditions

**Solutions:**

1. **Order hooks intentionally:**
   ```yaml
   hooks:
     - module: hooks-redaction    # Run FIRST (modify events)
     - module: hooks-logging      # Run AFTER (see redacted events)
   ```

2. **Document dependencies:**
   ```yaml
   hooks:
     # hooks-redaction must run before hooks-logging
     - module: hooks-redaction
     - module: hooks-logging
   ```

---

## Reference

### File Locations

| Hook | Path |
|------|------|
| hooks-logging | `amplifier-dev/amplifier-module-hooks-logging/` |
| hooks-backup | `amplifier-dev/amplifier-module-hooks-backup/` |
| hooks-approval | `amplifier-dev/amplifier-module-hooks-approval/` |
| hooks-redaction | `amplifier-dev/amplifier-module-hooks-redaction/` |
| Hook system | `amplifier-core/amplifier_core/hooks.py` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Hook** | Observability extension point |
| **Event** | Lifecycle occurrence |
| **Handler** | Function responding to event |
| **Emit** | Fire an event |
| **Auto-discovery** | Automatic module event detection |

### Related Guides

- [**Mount Plans Guide**](./mounts.md) - How hooks are loaded
- [**Orchestrators Guide**](./orchestrators.md) - Events emitted by orchestrators
- [**Tools Guide**](./tools.md) - Tool execution events
- [**Development Guide**](./development.md) - Creating custom hooks

---

## Quick Reference

### Choosing Hooks

```
Need visibility?
    └─ hooks-logging (always!)

Need recovery?
    └─ hooks-backup (production)

Need human approval?
    └─ hooks-approval (high-risk ops)

Need secret protection?
    └─ hooks-redaction (compliance)

Need cost control?
    └─ hooks-scheduler-cost-aware (budgets)

Need context monitoring?
    └─ hooks-status-context (long conversations)

Need better UX?
    └─ hooks-streaming-ui (interactive)
```

### Configuration Template

```yaml
hooks:
  # Always: Observability
  - module: hooks-logging
    source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
    config:
      level: "INFO"          # DEBUG | INFO | WARNING | ERROR
      output: "console"      # console | file | both
      auto_discover: true    # Auto-discover module events

  # Production: Safety
  - module: hooks-backup
    source: git+https://github.com/microsoft/amplifier-module-hooks-backup@main
    config:
      backup_dir: .amplifier/backups
      interval: 300          # Every 5 minutes
      max_backups: 10

  # Production: Security
  - module: hooks-redaction
    source: git+https://github.com/microsoft/amplifier-module-hooks-redaction@main
    config:
      enabled: true
      patterns:
        - '(sk-[a-zA-Z0-9]{48})'  # API keys
```

### Event Reference

```python
# Tool events
coordinator.hooks.emit("tool:invoked", {"tool_name": "read_file", ...})
coordinator.hooks.emit("tool:completed", {"tool_name": "read_file", ...})

# Session events
coordinator.hooks.emit("session:start", {})
coordinator.hooks.emit("session:end", {})

# Context events
coordinator.hooks.emit("context:compact:start", {})
coordinator.hooks.emit("context:usage:warning", {"percent": 85})

# Custom events
coordinator.hooks.emit("mymodule:custom", {"key": "value"})
```

---

**Hooks are the agent's nervous system. Use logging always, layer for safety, and auto-discover module events.**
