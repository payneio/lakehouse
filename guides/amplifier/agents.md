# Amplifier Agents Guide

**Comprehensive guide for understanding and working with Amplifier agents (sub-agents)**

---

## Table of Contents

1. [What Are Agents?](#what-are-agents)
2. [How Agents Work](#how-agents-work)
3. [Agent Configuration](#agent-configuration)
4. [Delegation Patterns](#delegation-patterns)
5. [Configuration](#configuration)
6. [Best Practices](#best-practices)
7. [Common Patterns](#common-patterns)
8. [Troubleshooting](#troubleshooting)
9. [Reference](#reference)

---

## What Are Agents?

**Agents** (also called "sub-agents") are named configuration overlays that define specialized agent personas. They allow a main agent to spawn child sessions with different capabilities, models, and instructions for specific tasks.

### Key Characteristics

- **Named configurations**: Pre-defined agent personalities
- **Task-specific**: Optimized for particular work types
- **Independent sessions**: Each runs in its own session
- **Configurable isolation**: Control which tools sub-agents can use
- **Result integration**: Sub-agent output returned to parent

### Philosophy

Agents embody the "delegation" principle:
- **Division of labor**: Right agent for the right task
- **Specialized expertise**: Each agent optimized for specific work
- **Parallel execution**: Multiple agents can work concurrently
- **Recursive prevention**: Control delegation depth

Think of it as: **Agents are the team - each member has a specialized role.**

---

## How Agents Work

### The Lifecycle

```
┌─────────────────────┐
│  1. Main Agent      │  User interacts with primary agent
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Task Identified │  Main agent decides to delegate
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Agent Selected  │  Choose appropriate sub-agent
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Session Spawned │  Create child session with agent config
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Agent Executes  │  Sub-agent works independently
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  6. Result Returned │  Output returned to main agent
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  7. Integration     │  Main agent uses result
└─────────────────────┘
```

### Integration with Session

```python
# Agents defined in mount plan
mount_plan = {
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple"
    },
    "tools": [
        {"module": "tool-filesystem"},
        {"module": "tool-task"}  # ← Enables delegation
    ],
    "agents": {  # ← Agent configurations
        "bug-hunter": {
            "description": "Specialized debugging agent",
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {
                        "model": "claude-opus-4-1"  # Stronger model
                    }
                }
            ],
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"}
                # Note: NO tool-task (prevent recursive delegation)
            ],
            "system": {
                "instruction": "You are a debugging specialist..."
            }
        }
    }
}

async with AmplifierSession(config=mount_plan) as session:
    # Main agent can delegate to bug-hunter
    response = await session.execute(
        "There's a crash in auth.py. Use bug-hunter to investigate."
    )

    # Behind the scenes:
    # 1. Main agent: spawn_task(agent_name="bug-hunter", task="Investigate crash")
    # 2. tool-task creates child session with bug-hunter config
    # 3. bug-hunter agent reads auth.py, analyzes, finds issue
    # 4. bug-hunter returns: "Found null pointer dereference at line 42"
    # 5. Main agent receives result and continues
```

---

## Agent Configuration

### Agent Structure

```python
{
    "agents": {
        "agent-name": {  # Agent identifier
            "description": str,              # Agent description (for selection)
            "session": dict,                 # Optional: session overrides
            "providers": list,               # Optional: provider overrides
            "tools": list,                   # Optional: tool overrides
            "hooks": list,                   # Optional: hook overrides
            "system": {"instruction": str}   # System instruction
        }
    }
}
```

### Configuration Inheritance

Agents inherit from parent session and can override:

**Parent session:**
```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple"
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "config": {"model": "claude-sonnet-4-5"}
        }
    ],
    "tools": [
        {"module": "tool-filesystem"},
        {"module": "tool-bash"},
        {"module": "tool-task"}
    ]
}
```

**Agent configuration:**
```python
{
    "agents": {
        "bug-hunter": {
            # Inherits: orchestrator, context from parent
            # Overrides: provider model
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {"model": "claude-opus-4-1"}  # Stronger!
                }
            ],
            # Overrides: tools (restricted set)
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"}
                # NO tool-task (prevent recursion)
            ],
            "system": {
                "instruction": "You are a debugging specialist..."
            }
        }
    }
}
```

**Resulting agent session:**
- Orchestrator: `loop-streaming` (inherited)
- Context: `context-simple` (inherited)
- Provider: `provider-anthropic` with `claude-opus-4-1` (overridden)
- Tools: `tool-filesystem`, `tool-bash` (overridden, task removed)
- System: Custom debugging instruction (overridden)

---

## Delegation Patterns

### Pattern 1: Task Specialization

**Use case:** Different agents for different task types

**Configuration:**
```yaml
agents:
  code-architect:
    description: "System design and architecture specialist"
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1      # Strongest reasoning
          temperature: 0.3            # More deterministic
    tools:
      - module: tool-filesystem
    system:
      instruction: |
        You are a software architect specializing in system design.
        Focus on scalability, maintainability, and best practices.

  bug-hunter:
    description: "Debugging and troubleshooting specialist"
    providers:
      - module: provider-anthropic
        config:
          model: claude-sonnet-4-5    # Fast, good at code
          temperature: 0.1            # Very deterministic
    tools:
      - module: tool-filesystem
      - module: tool-bash             # Can run tests
    system:
      instruction: |
        You are a debugging specialist.
        Systematically identify root causes and propose fixes.

  content-writer:
    description: "Documentation and content creation specialist"
    providers:
      - module: provider-openai
        config:
          model: gpt-4                # Good at creative writing
          temperature: 0.7            # More creative
    tools:
      - module: tool-filesystem
      - module: tool-web              # Can research
    system:
      instruction: |
        You are a technical writer specializing in clear documentation.
        Write for developers, balancing detail with accessibility.
```

**Usage:**
```python
# Main agent delegates appropriately
await session.execute("Design the authentication system using code-architect")
await session.execute("Debug the login crash using bug-hunter")
await session.execute("Write API docs using content-writer")
```

---

### Pattern 2: Model Selection

**Use case:** Use stronger/weaker models based on task complexity

**Configuration:**
```yaml
agents:
  quick-scout:
    description: "Fast analysis agent for simple tasks"
    providers:
      - module: provider-anthropic
        config:
          model: claude-haiku-3-5     # Fastest, cheapest
    tools:
      - module: tool-filesystem
    system:
      instruction: "Quick analysis only. Be concise."

  deep-analyzer:
    description: "Thorough analysis agent for complex tasks"
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1      # Strongest, most expensive
    tools:
      - module: tool-filesystem
      - module: tool-bash
    system:
      instruction: "Thorough analysis. Consider all edge cases."
```

**Usage:**
```python
# Cheap for simple tasks
await session.execute("Quick check: count files using quick-scout")

# Expensive for complex tasks
await session.execute("Deep analysis of concurrency issues using deep-analyzer")
```

---

### Pattern 3: Tool Restriction

**Use case:** Control which capabilities sub-agents have

**Configuration:**
```yaml
agents:
  read-only-analyst:
    description: "Analysis agent with no write permissions"
    tools:
      - module: tool-filesystem
        config:
          allowed_write_paths: []   # NO writing!
      - module: tool-search
    system:
      instruction: "Analyze code but make NO modifications."

  writer-agent:
    description: "Implementation agent that can modify files"
    tools:
      - module: tool-filesystem     # Full permissions
      - module: tool-bash
    system:
      instruction: "Implement changes as specified."
```

**Usage:**
```python
# Safe: can't break anything
await session.execute("Analyze codebase using read-only-analyst")

# Powerful: can modify
await session.execute("Implement the fix using writer-agent")
```

---

### Pattern 4: Preventing Recursion

**Critical pattern:** Prevent infinite delegation

**Configuration:**
```yaml
tools:
  - module: tool-task           # Main agent CAN delegate

agents:
  sub-agent:
    description: "Specialized agent"
    tools:
      - module: tool-filesystem
      - module: tool-bash
      # NO tool-task! Cannot delegate further
    system:
      instruction: "You are a specialized agent. Complete tasks yourself."
```

**Why critical:**
```
Without restriction:
Main → Sub-Agent-1 → Sub-Agent-2 → Sub-Agent-3 → ...
                                    (infinite recursion!)

With restriction:
Main → Sub-Agent
       (Sub-Agent completes task, returns)
```

---

## Configuration

### Mount Plan Configuration

```python
{
    "tools": [
        {"module": "tool-filesystem"},
        {"module": "tool-task"}  # Required for delegation
    ],
    "agents": {
        "bug-hunter": {
            "description": "Debugging specialist",
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {"model": "claude-opus-4-1"}
                }
            ],
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"}
            ],
            "system": {
                "instruction": "You are a debugging specialist..."
            }
        },
        "code-architect": {
            "description": "Architecture specialist",
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {
                        "model": "claude-opus-4-1",
                        "temperature": 0.3
                    }
                }
            ],
            "tools": [
                {"module": "tool-filesystem"}
            ],
            "system": {
                "instruction": "You are a software architect..."
            }
        }
    }
}
```

### Profile Configuration

```yaml
# profiles/dev.md
---
tools:
  - module: tool-filesystem
  - module: tool-bash
  - module: tool-task          # Enable delegation

agents:
  bug-hunter:
    description: "Debugging specialist"
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1
          temperature: 0.1
    tools:
      - module: tool-filesystem
      - module: tool-bash
      # NO tool-task
    system:
      instruction: |
        You are a debugging specialist.
        Systematically identify root causes.
---

You are a senior software engineer with access to specialized agents.
Use bug-hunter for debugging tasks.
```

---

## Best Practices

### 1. Design Clear Specializations

**Good: Clear, distinct roles**
```yaml
agents:
  test-writer:
    description: "Writes comprehensive tests"
    # Specialized for testing

  code-reviewer:
    description: "Reviews code for quality"
    # Specialized for review

  implementer:
    description: "Implements features from specs"
    # Specialized for implementation
```

**Bad: Overlapping, vague roles**
```yaml
agents:
  helper-1:
    description: "Does various things"
    # Too vague!

  helper-2:
    description: "Also does things"
    # What's the difference?
```

---

### 2. Control Costs with Model Selection

**Strategy: Use appropriate models for task complexity**

```yaml
agents:
  quick-tasks:
    providers:
      - module: provider-anthropic
        config:
          model: claude-haiku-3-5    # $0.25 per 1M tokens
    # For simple, routine tasks

  complex-tasks:
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1     # $15 per 1M tokens
    # Only for complex reasoning
```

**Savings:**
- 60x cost difference between Haiku and Opus
- Use Opus only when complexity justifies cost
- Most tasks work fine with Sonnet/Haiku

---

### 3. Always Prevent Recursion

**Critical: Remove tool-task from sub-agents**

```yaml
tools:
  - module: tool-task           # Main agent CAN delegate

agents:
  any-sub-agent:
    tools:
      - module: tool-filesystem
      - module: tool-bash
      # ❌ NO tool-task!
```

**Why:**
- Prevents infinite delegation chains
- Reduces complexity
- Saves costs (each level multiplies usage)
- Easier to debug

---

### 4. Use Descriptive Agent Names

**Good: Immediately clear purpose**
```yaml
agents:
  test-coverage-analyzer:     # Clear what it does
  security-audit-specialist:  # Clear what it does
  api-documentation-writer:   # Clear what it does
```

**Bad: Vague or generic**
```yaml
agents:
  agent1:     # What does it do?
  helper:     # What kind of help?
  specialist: # Specialist in what?
```

---

### 5. Document Agent Capabilities

```yaml
agents:
  bug-hunter:
    description: |
      Specialized debugging agent with:
      - Access to filesystem and bash
      - Claude Opus 4.1 for deep reasoning
      - Low temperature for determinism
      - Expert system prompt for systematic debugging

      Use for:
      - Investigating crashes
      - Finding root causes
      - Analyzing error logs
      - Proposing fixes

      Do NOT use for:
      - Simple code reading
      - Documentation writing
      - Routine tasks
```

---

## Common Patterns

### Pattern: Progressive Delegation

**Main agent → Scout → Specialist**

```yaml
agents:
  quick-scout:
    description: "Fast initial analysis (Haiku)"
    providers:
      - module: provider-anthropic
        config:
          model: claude-haiku-3-5    # Fast, cheap

  deep-specialist:
    description: "Deep analysis if needed (Opus)"
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1     # Slow, expensive
```

**Workflow:**
```python
# 1. Quick cheap check first
result = await session.execute("Quick scan with quick-scout: any obvious issues?")

# 2. If issues found, deep dive
if "issues found" in result:
    await session.execute("Deep analysis with deep-specialist")
```

---

### Pattern: Parallel Delegation

**Multiple agents working simultaneously**

```yaml
agents:
  security-auditor:
    description: "Security review"
  performance-analyzer:
    description: "Performance analysis"
  code-quality-checker:
    description: "Code quality review"
```

**Workflow:**
```python
# Main agent delegates all three in parallel
await session.execute("""
Run parallel reviews:
1. Security audit with security-auditor
2. Performance analysis with performance-analyzer
3. Code quality check with code-quality-checker

Combine results when all complete.
""")
```

---

### Pattern: Chain of Responsibility

**Agent delegates to more specialized agent**

```yaml
agents:
  general-engineer:
    description: "General development agent"
    tools:
      - module: tool-filesystem
      - module: tool-task        # CAN delegate further

  database-specialist:
    description: "Database expert"
    tools:
      - module: tool-filesystem
      # NO tool-task (end of chain)
```

**Workflow:**
```
User → Main Agent → general-engineer → database-specialist
                                       (end of chain)
```

---

## Troubleshooting

### Issue: Agent Not Found

**Error:** `Agent 'bug-hunter' not defined`

**Causes:**
1. Agent not in mount plan
2. Typo in agent name
3. Profile not compiled

**Solutions:**

1. **Verify agent defined:**
   ```yaml
   agents:
     bug-hunter:  # Must match exactly
       description: "..."
   ```

2. **Check spelling:**
   ```python
   # Wrong
   spawn_task(agent_name="bug_hunter")  # Underscore!

   # Right
   spawn_task(agent_name="bug-hunter")  # Hyphen
   ```

---

### Issue: Infinite Recursion

**Error:** `Maximum delegation depth exceeded`

**Causes:**
1. Sub-agent has tool-task
2. Agent delegates to itself
3. Circular delegation (A → B → A)

**Solutions:**

1. **Remove tool-task from sub-agents:**
   ```yaml
   agents:
     sub-agent:
       tools:
         - module: tool-filesystem
         # ❌ Remove: module: tool-task
   ```

2. **Implement depth limit:**
   ```yaml
   tools:
     - module: tool-task
       config:
         max_depth: 2  # Stop after 2 levels
   ```

---

### Issue: Agent Using Wrong Model

**Symptoms:**
- Agent slower/faster than expected
- Costs higher than expected
- Quality different than expected

**Causes:**
1. Agent config not overriding parent
2. Provider not specified
3. Inheritance not working

**Solutions:**

1. **Explicitly override provider:**
   ```yaml
   agents:
     my-agent:
       providers:
         - module: provider-anthropic
           config:
             model: claude-opus-4-1  # Explicit!
   ```

2. **Check inheritance:**
   ```python
   # Enable debug logging
   hooks:
     - module: hooks-logging
       config:
         level: DEBUG  # See agent config
   ```

---

### Issue: Agent Can't Use Tools

**Error:** `Tool 'read_file' not available`

**Causes:**
1. Tool not in agent's tools list
2. Tool restricted (paths, permissions)
3. Tool requires approval

**Solutions:**

1. **Add tool to agent:**
   ```yaml
   agents:
     my-agent:
       tools:
         - module: tool-filesystem  # Add this!
   ```

2. **Check tool config:**
   ```yaml
   agents:
     my-agent:
       tools:
         - module: tool-filesystem
           config:
             allowed_write_paths: ["."]  # Verify paths
   ```

---

## Reference

### File Locations

| Component | Path |
|-----------|------|
| tool-task | `amplifier-dev/amplifier-module-tool-task/` |
| Agent spawning | `amplifier-core/amplifier_core/coordinator.py` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | Named configuration overlay for specialized tasks |
| **Delegation** | Main agent spawning sub-agent |
| **Inheritance** | Sub-agent inheriting from parent session |
| **Override** | Sub-agent changing inherited config |
| **Recursion** | Agent delegating to another agent |

### Related Guides

- [**Mount Plans Guide**](./mounts.md) - Agent configuration structure
- [**Tools Guide**](./tools.md) - tool-task enables delegation
- [**Profiles Guide**](./profiles.md) - Defining agents in profiles

---

## Quick Reference

### Agent Configuration Template

```yaml
agents:
  agent-name:
    description: "Clear description of agent's purpose and capabilities"

    # Optional: Override provider
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1    # Or sonnet, haiku
          temperature: 0.3          # 0.0-1.0

    # Optional: Override tools
    tools:
      - module: tool-filesystem
      - module: tool-bash
      # ❌ NO tool-task (prevent recursion)

    # Optional: Override hooks
    hooks:
      - module: hooks-logging
        config:
          level: DEBUG

    # Required: System instruction
    system:
      instruction: |
        You are a specialized agent for [specific task].

        Your capabilities:
        - [capability 1]
        - [capability 2]

        Your responsibilities:
        - [responsibility 1]
        - [responsibility 2]
```

### Delegation Example

```python
# In main agent
response = await session.execute("""
Investigate the authentication bug using bug-hunter agent.

Steps:
1. Read auth.py
2. Analyze the login flow
3. Identify the bug
4. Propose a fix
""")

# Behind the scenes:
# LLM: spawn_task(agent_name="bug-hunter", task="Investigate auth bug...")
# tool-task: Creates child session with bug-hunter config
# bug-hunter: Executes independently
# tool-task: Returns result to main agent
```

---

**Agents are the team. Specialize roles, control costs, prevent recursion, and delegate wisely.**
