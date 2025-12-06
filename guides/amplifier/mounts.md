# Amplifier Mount Plans Guide

**Comprehensive technical guide for developers working with Amplifier mount plans**

---

## Table of Contents

1. [What Are Mount Plans?](#what-are-mount-plans)
2. [How Mount Plans Work](#how-mount-plans-work)
3. [Mount Plan Structure](#mount-plan-structure)
4. [From Profile to Mount Plan](#from-profile-to-mount-plan)
5. [Module Mounting](#module-mounting)
6. [Configuration Examples](#configuration-examples)
7. [Validation](#validation)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Mount Plans?

A **Mount Plan** is the contract between the application layer (CLI) and the Amplifier kernel (amplifier-core). It defines exactly what modules should be loaded and how they should be configured for a session.

### Key Characteristics

- **Kernel contract**: The single format the kernel understands
- **Resolved configuration**: All profile inheritance, merging, and resolution completed
- **Complete specification**: Contains all modules, sources, and configuration
- **JSON-serializable**: Plain Python dictionary structure
- **Validation target**: Kernel validates mount plans before loading modules

### Philosophy

Mount plans embody the "mechanism vs policy" separation:
- **App layer (CLI)**: Creates mount plans (policy decisions)
- **Kernel (amplifier-core)**: Executes mount plans (mechanisms only)
- **Profiles**: High-level policy that compiles to mount plans

Think of it as: **Profiles are the blueprint, Mount Plans are the build instructions.**

---

## How Mount Plans Work

### The Lifecycle

```
┌─────────────────────┐
│  1. User Intent     │  Command + flags + env vars
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Profile Loading │  Load profile + resolve inheritance
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Settings Merge  │  Merge local/project/global settings
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Compilation     │  Compile to Mount Plan (this guide!)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Kernel Receives │  AmplifierSession validates + loads
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  6. Module Loading  │  Kernel loads and mounts modules
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  7. Session Ready   │  Ready to execute prompts
└─────────────────────┘
```

### Who Creates Mount Plans?

**App layer** creates mount plans:
- CLI: `amplifier-app-cli` compiles profiles to mount plans
- Custom apps: Your code compiles your config to mount plans
- Libraries: `amplifier-profiles` provides `compile_profile_to_mount_plan()`

**Kernel** receives mount plans:
- `AmplifierSession(config=mount_plan)` validates and executes
- Never creates or modifies mount plans
- Only mechanism: loading modules per the plan

---

## Mount Plan Structure

### Complete Schema

```python
{
    # Required: Session configuration
    "session": {
        "orchestrator": str,              # Required: orchestrator module ID
        "orchestrator_source": str,       # Optional: source URI
        "context": str,                   # Required: context module ID
        "context_source": str,            # Optional: source URI
        "injection_budget_per_turn": int, # Optional: max tokens per turn (default: 10000)
        "injection_size_limit": int       # Optional: max bytes per injection (default: 10240)
    },

    # Optional: Orchestrator configuration
    "orchestrator": {
        "config": dict  # Orchestrator-specific settings
    },

    # Optional: Context configuration
    "context": {
        "config": dict  # Context-specific settings
    },

    # Optional: Provider list
    "providers": [
        {
            "module": str,   # Required: provider module ID
            "source": str,   # Optional: source URI (git, file, package)
            "config": dict   # Optional: provider-specific config
        }
    ],

    # Optional: Tool list
    "tools": [
        {
            "module": str,   # Required: tool module ID
            "source": str,   # Optional: source URI
            "config": dict   # Optional: tool-specific config
        }
    ],

    # Optional: Hook list
    "hooks": [
        {
            "module": str,   # Required: hook module ID
            "source": str,   # Optional: source URI
            "config": dict   # Optional: hook-specific config
        }
    ],

    # Optional: Agent configuration overlays (app-layer data)
    "agents": {
        "<agent-name>": {
            "description": str,              # Agent description
            "session": dict,                 # Optional: session overrides
            "providers": list,               # Optional: provider overrides
            "tools": list,                   # Optional: tool overrides
            "hooks": list,                   # Optional: hook overrides
            "system": {"instruction": str}   # System instruction
        }
    }
}
```

### Required Fields

**Minimum valid mount plan**:
```python
{
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {"module": "provider-mock"}
    ]
}
```

### Module Sources

**Source URI formats**:
- Git: `git+https://github.com/org/repo@ref`
- File: `file:///absolute/path` or `/absolute/path` or `./relative/path`
- Package: `package-name` (or omit source to use installed package)

**Resolution**:
- If `source` provided: ModuleSourceResolver resolves it
- If omitted: Falls back to installed packages via entry points

---

## From Profile to Mount Plan

### The Compilation Process

**Input**: Profile (YAML + Markdown)
```yaml
# profiles/dev.md
---
profile:
  name: dev
  version: 1.0.0
  extends: foundation:base

providers:
  - module: provider-anthropic
    config:
      debug: true

tools:
  - module: tool-filesystem
---
System instruction here...
```

**Output**: Mount Plan (Python dict)
```python
{
    "session": {
        "orchestrator": "loop-streaming",  # From base profile
        "orchestrator_source": "git+https://...",
        "context": "context-simple",
        "context_source": "git+https://..."
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://...",  # Inherited from base
            "config": {
                "model": "claude-sonnet-4-5",  # From base
                "debug": True  # From dev (merged)
            }
        }
    ],
    "tools": [
        {
            "module": "tool-web",
            "source": "git+https://..."  # From base
        },
        {
            "module": "tool-filesystem",
            "source": "git+https://..."  # From dev
        }
    ]
}
```

### Using the Compiler

```python
from amplifier_profiles import ProfileLoader, compile_profile_to_mount_plan
from pathlib import Path

# Step 1: Load profile (with inheritance resolved)
loader = ProfileLoader(search_paths=[...])
profile = loader.load_profile("dev")

# Step 2: Compile to mount plan
mount_plan = compile_profile_to_mount_plan(profile, agent_loader=None)

# Step 3: Use with kernel
from amplifier_core import AmplifierSession

async with AmplifierSession(config=mount_plan) as session:
    response = await session.execute("Hello!")
```

### What Gets Compiled

**From profile to mount plan**:

| Profile Element | Mount Plan Element | Notes |
|----------------|-------------------|-------|
| `session.orchestrator` | `session.orchestrator` | Direct copy |
| `session.context` | `session.context` | Direct copy |
| `providers` | `providers` | Deep merge by module ID |
| `tools` | `tools` | Deep merge by module ID |
| `hooks` | `hooks` | Deep merge by module ID |
| `agents` | `agents` | Pass through (app-layer data) |
| Markdown body | Injected into system instruction | Via context loading |

### Deep Merging

**Parent profile**:
```yaml
providers:
  - module: provider-anthropic
    source: git+https://...
    config:
      model: claude-sonnet-4-5
      temperature: 0.7
```

**Child profile**:
```yaml
providers:
  - module: provider-anthropic
    config:
      debug: true
```

**Compiled mount plan**:
```python
{
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://...",  # Inherited!
            "config": {
                "model": "claude-sonnet-4-5",  # From parent
                "temperature": 0.7,            # From parent
                "debug": True                  # From child (merged)
            }
        }
    ]
}
```

---

## Module Mounting

### Mount Points

The kernel manages these mount points:

| Mount Point | Cardinality | Purpose | Access |
|-------------|-------------|---------|--------|
| `orchestrator` | Single | Execution loop | `coordinator.orchestrator` |
| `context` | Single | Memory management | `coordinator.context` |
| `providers` | Multiple (dict) | LLM backends | `coordinator.providers[id]` |
| `tools` | Multiple (dict) | Agent capabilities | `coordinator.tools[id]` |
| `hooks` | Multiple (registry) | Observability | `coordinator.hooks` |

### Mounting Flow

```
Mount Plan provided
    ↓
Kernel validates structure
    ↓
ModuleLoader discovers modules
    ↓
For each module:
    ├─ Resolve source (if provided)
    ├─ Import module package
    ├─ Call module.mount(coordinator, config)
    ├─ Module mounts itself at appropriate point
    └─ Store cleanup function (if returned)
    ↓
All modules mounted
    ↓
Session ready to execute
```

### Module Loading Order

1. **Context manager** (memory required first)
2. **Orchestrator** (execution loop)
3. **Providers** (LLM backends)
4. **Tools** (agent capabilities)
5. **Hooks** (observability, can observe loading)

### Special Semantics: agents Section

**Other sections** (`providers`, `tools`, `hooks`):
- Lists of modules to load NOW during session initialization
- Kernel loads and mounts these modules

**agents section**:
- Dict of named configuration overlays (app-layer data)
- NOT modules to mount during initialization
- Used by app layer (task tool) for spawning child sessions
- Kernel passes through without interpretation

---

## Configuration Examples

### Minimal Mount Plan

**Absolute minimum**:
```python
{
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {"module": "provider-mock"}
    ]
}
```

Creates:
- Simple orchestrator loop
- In-memory context (no persistence)
- Mock provider (for testing)

### Development Mount Plan

**Typical development configuration**:
```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "orchestrator_source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",
        "context": "context-persistent",
        "context_source": "git+https://github.com/microsoft/amplifier-module-context-persistent@main"
    },
    "context": {
        "config": {
            "max_tokens": 200000,
            "compact_threshold": 0.92,
            "auto_compact": True
        }
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
            "config": {
                "model": "claude-sonnet-4-5",
                "api_key": "${ANTHROPIC_API_KEY}",
                "debug": True
            }
        }
    ],
    "tools": [
        {
            "module": "tool-filesystem",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-filesystem@main",
            "config": {
                "allowed_paths": ["."],
                "require_approval": False
            }
        },
        {
            "module": "tool-bash",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-bash@main"
        },
        {
            "module": "tool-web",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-web@main"
        }
    ],
    "hooks": [
        {
            "module": "hooks-logging",
            "source": "git+https://github.com/microsoft/amplifier-module-hooks-logging@main",
            "config": {
                "output_dir": ".amplifier/logs",
                "mode": "session-only"
            }
        }
    ]
}
```

### Production Mount Plan

**Production configuration with safety and cost controls**:
```python
{
    "session": {
        "orchestrator": "loop-events",
        "orchestrator_source": "git+https://github.com/microsoft/amplifier-module-loop-events@main",
        "context": "context-persistent",
        "context_source": "git+https://github.com/microsoft/amplifier-module-context-persistent@main",
        "injection_budget_per_turn": 500,   # Conservative limit
        "injection_size_limit": 8192         # 8KB cap
    },
    "context": {
        "config": {
            "max_tokens": 200000,
            "compact_threshold": 0.95,
            "auto_compact": True
        }
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
            "config": {
                "model": "claude-sonnet-4-5",
                "api_key": "${ANTHROPIC_API_KEY}",
                "max_tokens": 4096,
                "debug": False
            }
        }
    ],
    "tools": [
        {
            "module": "tool-filesystem",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-filesystem@main",
            "config": {
                "allowed_paths": ["/app/data"],
                "require_approval": True  # Safety
            }
        }
    ],
    "hooks": [
        {
            "module": "hooks-logging",
            "source": "git+https://github.com/microsoft/amplifier-module-hooks-logging@main",
            "config": {
                "mode": "all",
                "redaction_enabled": True
            }
        },
        {
            "module": "hooks-backup",
            "source": "git+https://github.com/microsoft/amplifier-module-hooks-backup@main"
        }
    ]
}
```

### Agent Delegation Mount Plan

**With agent configurations for task delegation**:
```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple"
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
            "config": {
                "model": "claude-sonnet-4-5"
            }
        }
    ],
    "tools": [
        {"module": "tool-filesystem", "source": "git+https://..."},
        {"module": "tool-task", "source": "git+https://..."}  # Enables delegation
    ],
    "agents": {
        "bug-hunter": {
            "description": "Specialized debugging agent",
            "providers": [
                {
                    "module": "provider-anthropic",
                    "config": {
                        "model": "claude-opus-4-1",  # Override to Opus
                        "temperature": 0.3
                    }
                }
            ],
            "tools": [
                {"module": "tool-filesystem"},
                {"module": "tool-bash"}
                # Note: no tool-task (prevent recursive delegation)
            ],
            "system": {
                "instruction": "You are a debugging specialist..."
            }
        }
    }
}
```

---

## Validation

### What Kernel Validates

`AmplifierSession` validates mount plans on initialization:

**Required fields**:
- `session.orchestrator` must be present and loadable
- `session.context` must be present and loadable
- At least one provider must be configured

**Module loading**:
- All specified module IDs must be discoverable
- Module loading failures logged but non-fatal (except orchestrator/context)
- Invalid config for a module causes that module to skip loading

**Error handling**:
- Missing required fields: `ValueError` raised immediately
- Module not found: Logged as warning, session continues
- Invalid module config: Logged as warning, module skipped

### Validation Example

```python
from amplifier_core import AmplifierSession

# Valid mount plan
valid_plan = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [{"module": "provider-mock"}]
}

async with AmplifierSession(config=valid_plan) as session:
    # Success!
    pass

# Invalid mount plan (missing orchestrator)
invalid_plan = {
    "session": {
        "context": "context-simple"
    },
    "providers": [{"module": "provider-mock"}]
}

async with AmplifierSession(config=invalid_plan) as session:
    # Raises: ValueError("session.orchestrator is required")
    pass
```

---

## Best Practices

### 1. Always Include Sources in Root Profiles

**Don't rely on inheritance for sources**:
```python
# BAD: Missing source in root profile
{
    "providers": [
        {
            "module": "provider-anthropic",
            "config": {"model": "claude-sonnet-4-5"}
            # Missing source!
        }
    ]
}
```

**Include sources explicitly**:
```python
# GOOD: Source specified
{
    "providers": [
        {
            "module": "provider-anthropic",
            "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
            "config": {"model": "claude-sonnet-4-5"}
        }
    ]
}
```

**Why**: Sources can be inherited in child profiles, but root profiles must be complete.

### 2. Use Environment Variables for Secrets

**Don't hardcode API keys**:
```python
# BAD: Hardcoded secret
{
    "providers": [{
        "module": "provider-anthropic",
        "config": {
            "api_key": "sk-ant-actual-key-here"  # Bad!
        }
    }]
}
```

**Use environment variables**:
```python
# GOOD: Environment variable
{
    "providers": [{
        "module": "provider-anthropic",
        "config": {
            "api_key": "${ANTHROPIC_API_KEY}"  # Good!
        }
    }]
}
```

### 3. Set Appropriate Injection Limits

**Production should have conservative limits**:
```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-persistent",
        "injection_budget_per_turn": 500,   # 500 tokens max
        "injection_size_limit": 8192         # 8KB max
    }
}
```

**Development can be more permissive**:
```python
{
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple",
        "injection_budget_per_turn": 10000,  # Default
        "injection_size_limit": 10240        # Default
    }
}
```

### 4. Organize Module Config Logically

**Group related config**:
```python
{
    "context": {
        "config": {
            # Memory management
            "max_tokens": 200000,
            "compact_threshold": 0.92,
            "auto_compact": True,

            # Persistence
            "storage_path": ".amplifier/context"
        }
    }
}
```

### 5. Document Custom Mount Plans

**Add comments explaining choices**:
```python
mount_plan = {
    "session": {
        "orchestrator": "loop-events",  # Events for production observability
        "context": "context-persistent",  # Persistence required
        "injection_budget_per_turn": 500  # Conservative for cost control
    },
    # ... rest of plan
}
```

---

## Troubleshooting

### Issue: Module Not Found

**Error**: `Module 'tool-xyz' not found`

**Check**:
1. Source specified in mount plan
2. Source URI correct and accessible
3. Module exports correct entry point

**Solution**:
```python
# Add source
{
    "tools": [
        {
            "module": "tool-xyz",
            "source": "git+https://github.com/org/tool-xyz@main",  # Add this
            "config": {}
        }
    ]
}
```

### Issue: Invalid Config

**Error**: `Invalid config for module 'provider-anthropic'`

**Check**:
1. Config keys match module documentation
2. Values are correct types
3. Required keys present

**Solution**:
```python
# Check module docs for correct config schema
{
    "providers": [{
        "module": "provider-anthropic",
        "config": {
            "model": "claude-sonnet-4-5",  # String, not int
            "api_key": "${ANTHROPIC_API_KEY}",  # Required
            "temperature": 0.7  # Float, not string
        }
    }]
}
```

### Issue: Orchestrator/Context Failed to Load

**Error**: `Failed to load orchestrator 'loop-xyz'`

**Impact**: Session initialization fails (fatal error)

**Check**:
1. Orchestrator/context module exists
2. Source correct
3. Module compatible with kernel version

**Solution**:
```python
# Use known-good module
{
    "session": {
        "orchestrator": "loop-streaming",  # Use stable module
        "orchestrator_source": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"
    }
}
```

### Issue: Provider Not Found

**Error**: `No providers loaded`

**Impact**: Agent loop cannot execute (fatal)

**Check**:
1. At least one provider in `providers` list
2. Provider module loadable
3. Provider config valid

**Solution**:
```python
# Ensure at least one provider
{
    "providers": [
        {
            "module": "provider-mock",  # Fallback for testing
            "source": "git+https://github.com/microsoft/amplifier-module-provider-mock@main"
        }
    ]
}
```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| Mount plan spec | `amplifier-core/docs/specs/MOUNT_PLAN_SPECIFICATION.md` |
| Profile compiler | `amplifier-profiles/amplifier_profiles/compiler.py` |
| Session initialization | `amplifier-core/amplifier_core/session.py` |
| Module loader | `amplifier-core/amplifier_core/loader.py` |

### Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `compile_profile_to_mount_plan()` | Profile → mount plan | `amplifier-profiles` |
| `AmplifierSession(config=...)` | Mount plan → session | `amplifier-core` |
| `ModuleLoader.load()` | Module discovery/loading | `amplifier-core` |

### Related Guides

- [**Profiles Guide**](./profiles.md) - High-level configuration
- [**Modules Guide**](./modules.md) - Module system
- [**CLI Guide**](./cli.md) - Using profiles via CLI
- [**Development Guide**](./development.md) - Development workflows and custom modules

---

## Quick Reference

### Minimal Mount Plan Template

```python
{
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {"module": "provider-mock"}
    ]
}
```

### Complete Mount Plan Template

```python
{
    "session": {
        "orchestrator": str,
        "orchestrator_source": str,
        "context": str,
        "context_source": str,
        "injection_budget_per_turn": int,
        "injection_size_limit": int
    },
    "orchestrator": {"config": {}},
    "context": {"config": {}},
    "providers": [{"module": str, "source": str, "config": {}}],
    "tools": [{"module": str, "source": str, "config": {}}],
    "hooks": [{"module": str, "source": str, "config": {}}],
    "agents": {
        "agent-name": {
            "description": str,
            "session": {},
            "providers": [],
            "tools": [],
            "hooks": [],
            "system": {"instruction": str}
        }
    }
}
```

### Profile → Mount Plan Flow

```
Profile (YAML + Markdown)
    ↓ load with inheritance
Resolved Profile (Python dict)
    ↓ compile
Mount Plan (Python dict)
    ↓ provide to kernel
AmplifierSession (validates + loads)
    ↓ ready
Execute Prompts
```

---

**For more information**, see the [Mount Plan Specification](../amplifier-core/docs/specs/MOUNT_PLAN_SPECIFICATION.md).
