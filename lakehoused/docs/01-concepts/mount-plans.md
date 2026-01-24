# Mount Plans

**Runtime configuration format for amplifier-core**

---

## What is a Mount Plan?

A mount plan is the **configuration dict** that amplifier-core uses to initialize a session. It's generated from a profile when you create a session.

**Profile → Mount Plan → Session**

```yaml
# Profile (what you write)
session:
  orchestrator:
    module: loop-streaming
    config: {...}
```

```json
// Mount Plan (what gets generated)
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "foundation/base",
      "config": {...}
    }
  }
}
```

```python
# Session (what runs)
session = AmplifierSession(config=mount_plan)
await session.initialize()
```

---

## Why Mount Plans Exist

**Problem**: Profiles and amplifier-core speak different languages
- **Profiles**: User-friendly, reference external resources, use git URLs
- **Amplifier-core**: Needs module IDs, configuration dicts, no URLs

**Solution**: Mount plans are the **translation layer**
- Generated from profiles
- Format amplifier-core understands
- Contains runtime hints for module resolution

---

## Mount Plan Format

### Complete Example

```json
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "foundation/base",
      "config": {
        "extended_thinking": true,
        "max_iterations": 25
      }
    },
    "context": {
      "module": "context-simple",
      "source": "foundation/base",
      "config": {
        "max_tokens": 400000,
        "auto_compact": true
      }
    }
  },

  "providers": [
    {
      "module": "provider-anthropic",
      "source": "foundation/base",
      "config": {
        "default_model": "claude-sonnet-4-5"
      }
    }
  ],

  "tools": [
    {
      "module": "tool-web",
      "source": "foundation/base",
      "config": {}
    }
  ],

  "hooks": [
    {
      "module": "hooks-logging",
      "source": "foundation/base",
      "config": {
        "mode": "session-only"
      }
    }
  ],

  "agents": {
    "code-expert": {
      "content": "You are an expert software engineer...",
      "metadata": {
        "source": "foundation:agents/code-expert.md"
      }
    }
  }
}
```

---

## Key Components

### 1. Session Block (Required)

**Orchestrator and context** - the two required kernel modules:

```json
"session": {
  "orchestrator": {
    "module": "loop-streaming",    // Module ID
    "source": "foundation/base",   // Profile hint for resolver
    "config": {...}                // Module-specific config
  },
  "context": {
    "module": "context-simple",
    "source": "foundation/base",
    "config": {...}
  }
}
```

**Why required?**
- Orchestrator: Without it, the agent can't execute
- Context: Without it, the agent has no memory

### 2. Providers Array (Required, 1+)

**LLM providers** - at least one required:

```json
"providers": [
  {
    "module": "provider-anthropic",
    "source": "foundation/base",
    "config": {
      "default_model": "claude-sonnet-4-5",
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  }
]
```

**Why required?**
- AI needs a language model to function
- Can have multiple providers (fallback, model selection)

### 3. Tools Array (Optional)

**Capabilities** the AI can use:

```json
"tools": [
  {"module": "tool-web", "source": "foundation/base", "config": {}},
  {"module": "tool-filesystem", "source": "foundation/base", "config": {}}
]
```

**Why optional?**
- Some sessions don't need external tools
- Can start minimal, add tools as needed

### 4. Hooks Array (Optional)

**Lifecycle extensions**:

```json
"hooks": [
  {
    "module": "hooks-logging",
    "source": "foundation/base",
    "config": {"mode": "session-only"}
  }
]
```

### 5. Agents Dict (Optional)

**Embedded agent personas**:

```json
"agents": {
  "code-expert": {
    "content": "You are an expert software engineer specialized in...",
    "metadata": {
      "source": "foundation:agents/code-expert.md"
    }
  }
}
```

**Key difference**: Agents are **embedded content**, not modules to load.

---

## Profile Hints: The `source` Field

The **critical innovation** in mount plans is the `source` field:

```json
{
  "module": "provider-anthropic",
  "source": "foundation/base"    // ← Profile hint, NOT a filesystem path
}
```

**What is "foundation/base"?**
- It's a **hint** about where the module came from
- Format: `{collection}/{profile}`
- NOT an absolute path (keeps mount plans portable)

**How it's used:**
```python
# At runtime, the DaemonModuleSourceResolver translates:
"foundation/base" + "provider-anthropic"
    ↓
.lakehoused/share/profiles/foundation/base/providers/provider-anthropic/
```

**Why not absolute paths?**
- **Portable**: Mount plans work on any machine
- **Relocatable**: Share directory can move
- **Cleaner**: Less repetitive path information
- **Testable**: Easier to mock resolution

---

## Profiles vs. Mount Plans

| Aspect | Profile | Mount Plan |
|--------|---------|------------|
| **Format** | Markdown + YAML | JSON dict |
| **Audience** | Humans | amplifier-core |
| **Module refs** | Git URLs | Module IDs + hints |
| **Agents** | URLs to markdown | Embedded content |
| **Purpose** | Definition | Execution |
| **When** | Authored once | Generated per session |
| **Location** | registry/ | state/sessions/{id}/ |

---

## How Mount Plans are Generated

**When?** Every time you create a session

**Process:**
```python
# 1. Load profile from registry
profile = read_profile("foundation/base.md")

# 2. Parse YAML frontmatter
frontmatter = parse_yaml(profile)

# 3. Transform to mount plan dict
mount_plan = {
    "session": {
        "orchestrator": {
            "module": frontmatter["session"]["orchestrator"]["module"],
            "source": "foundation/base",  # Profile hint
            "config": frontmatter["session"]["orchestrator"]["config"]
        }
    },
    # ... same for other sections
}

# 4. Load agent content
mount_plan["agents"] = {}
for name, url in frontmatter.get("agents", {}).items():
    content = fetch(url)
    mount_plan["agents"][name] = {
        "content": content,
        "metadata": {"source": f"foundation:agents/{name}.md"}
    }

# 5. Save to session directory
save(f".lakehoused/state/sessions/{session_id}/mount_plan.json", mount_plan)
```

**Result**: A mount plan ready for amplifier-core

---

## Module Resolution at Runtime

**The magic of profile hints:**

```json
// Mount plan says:
{
  "module": "loop-streaming",
  "source": "foundation/base"
}
```

```python
# Resolver translates:
resolver = DaemonModuleSourceResolver(share_dir)
source = resolver.resolve("loop-streaming", "foundation/base")
path = source.resolve()

# Returns:
# .lakehoused/share/profiles/foundation/base/orchestrator/loop-streaming/
```

**Then ModuleLoader:**
1. Adds path to sys.path
2. Converts name: `loop-streaming` → `amplifier_module_loop_streaming`
3. Imports the Python package
4. Calls the mount function

---

## Directory Structure Contract

The resolver expects this structure:

```
.lakehoused/share/profiles/foundation/base/
├── orchestrator/
│   └── loop-streaming/                        ← Resolver finds this
│       └── amplifier_module_loop_streaming/   ← Python imports this
│           ├── __init__.py
│           └── orchestrator.py
```

**Two directories:**
- **Outer** (`loop-streaming/`): Profile name, what resolver returns
- **Inner** (`amplifier_module_loop_streaming/`): Python package name, what gets imported

---

## Mount Plan Storage

**Where:** `.lakehoused/state/sessions/{session_id}/mount_plan.json`

**When saved:**
- At session creation
- Contains all resolved configuration
- Used by ExecutionRunner to initialize AmplifierSession

**Format:**
```json
{
  "session": {...},
  "providers": [...],
  "tools": [...],
  "hooks": [...],
  "agents": {...}
}
```

**Why save it?**
- Sessions can be resumed
- Debugging: inspect exact configuration used
- Audit: know what modules were loaded

---

## Validation Rules

Mount plans must satisfy amplifier-core's requirements:

**Required:**
- `session.orchestrator` must exist
- `session.context` must exist
- `providers` must have at least one entry

**Optional:**
- `tools` defaults to `[]`
- `hooks` defaults to `[]`
- `agents` defaults to `{}`

**Module loading behavior:**
- **Orchestrator/context failure**: Fatal error, session won't start
- **Provider failure**: Warning, continues if other providers exist
- **Tool/hook failure**: Warning, continues (graceful degradation)

---

## Example Transformation

**Profile (input):**
```yaml
session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/org/modules@v1.0.0
    config:
      extended_thinking: true

providers:
- module: provider-anthropic
  source: git+https://github.com/org/modules@v1.0.0

agents:
  code-expert: https://example.com/code.md
```

**Mount Plan (output):**
```json
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "foundation/base",
      "config": {"extended_thinking": true}
    },
    "context": {
      "module": "context-simple",
      "source": "foundation/base",
      "config": {}
    }
  },
  "providers": [
    {
      "module": "provider-anthropic",
      "source": "foundation/base",
      "config": {}
    }
  ],
  "tools": [],
  "hooks": [],
  "agents": {
    "code-expert": {
      "content": "You are an expert...",
      "metadata": {"source": "foundation:agents/code-expert.md"}
    }
  }
}
```

**Key transformations:**
1. Git URL → Profile hint (`"foundation/base"`)
2. Agent URL → Embedded content
3. Structure normalized for amplifier-core

---

## Integration with Amplifier-Core

**Flow in ExecutionRunner:**

```python
# 1. Load mount plan
with open(f"sessions/{session_id}/mount_plan.json") as f:
    mount_plan = json.load(f)

# 2. Create session
session = AmplifierSession(config=mount_plan)

# 3. Mount resolver (translates hints → paths)
resolver = DaemonModuleSourceResolver(share_dir)
await session.coordinator.mount("module-source-resolver", resolver)

# 4. Initialize (loads modules using resolver)
await session.initialize()

# 5. Ready to execute!
response = await session.execute("Hello!")
```

**The resolver is the bridge** between profile hints and filesystem paths.

---

## Debugging Mount Plans

**View a mount plan:**
```bash
cat .lakehoused/state/sessions/{session-id}/mount_plan.json | jq
```

**Common issues:**

**Missing module:**
```
ValueError: Module 'provider-anthropic' not found
```
→ Check: `.lakehoused/share/profiles/foundation/base/providers/provider-anthropic/` exists

**Invalid config:**
```
RuntimeError: Cannot initialize without orchestrator
```
→ Check: Mount plan has `session.orchestrator`

**Resolution failure:**
```
ValueError: Could not determine mount type for module: my-custom-thing
```
→ Module ID must follow naming conventions (`provider-*`, `tool-*`, etc.)

---

## Next Steps

**Understand the complete flow:**
- Read [Profile Lifecycle](../04-advanced/profile-lifecycle.md)

**Learn about module resolution:**
- Read [Resolution](../04-advanced/resolution.md)

**See profile structure:**
- Back to [Profiles](profiles.md)
