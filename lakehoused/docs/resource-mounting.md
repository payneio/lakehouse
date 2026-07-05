# Resource Mounting Lifecycle Design

## Executive Summary

This document defines the data flow from `collections.yaml` through to amplifier-core mount plans. It specifies WHAT happens at each phase and WHAT format each artifact takes.

**Key Principle**: Resources flow through three phases—extraction, resolution, and mount plan generation—with identity preserved throughout.

---

## Core Concepts

### Resource Identity

Every resource has three forms of identity:

1. **Profile name** (user-facing): `loop-streaming`, `provider-anthropic`
   - Hyphenated, simple names
   - Used in profile specs and mount plans
   - What users see and configure

2. **Package name** (Python): `amplifier_module_loop_streaming`, `amplifier_module_provider_anthropic`
   - Underscore form required by Python
   - What's in git repos and on disk
   - What Python imports

3. **Mount type** (organizational): `orchestrator`, `context`, `providers`, `tools`, `hooks`, `agents`
   - Directory categories for organization
   - Determines structure in profile directory
   - Maps to amplifier-core's expected keys

**Module Naming Contract:**
```
Profile name:  "loop-streaming"                      (user-facing, in mount plans)
      ↓
Package name:  "amplifier_module_loop_streaming"   (Python import, on disk)
      ↓
Directory:     orchestrator/loop-streaming/          (organizational structure)
                 amplifier_module_loop_streaming/    (actual Python package inside)
```

### Resource Types

**Kernel Resources** (mounted during session initialization):
- `orchestrator`: One required, the execution loop module
- `context`: One required, the context manager module
- `providers`: Zero or more optional, LLM provider modules
- `tools`: Zero or more optional, tool modules
- `hooks`: Zero or more optional, hook modules

**App-Layer Data** (embedded in mount plan, not mounted as modules):
- `agents`: Zero or more optional, markdown content for agent personas
  - Agents ARE compiled into mount plans as embedded content
  - Available in `session.config["agents"]` dict
  - amplifier-core passes them through without interpretation

**Context Directories** (NOT in mount plans, loaded at runtime via @mentions):
- Collections MAY contain `context/` directories with markdown files
- These are NOT compiled into mount plans
- Loaded on-demand via @mention resolution (app-layer feature)
- Injected as messages via `context.add_message()` API
- amplifier-core is completely unaware of context files or @mentions
- Example: `@foundation:context/IMPLEMENTATION_PHILOSOPHY.md`

**Key Distinction**:
- **Agents**: Compiled → Mount plan → Kernel sees as config data
- **Context**: Referenced via @mentions → Loaded at runtime → Kernel sees as messages

---

## Three-Phase Lifecycle

### Phase 1: Profile Extraction

**Purpose**: Extract profile specs from collections and cache git content

**Input**: `.lakehoused/share/collections.yaml`
```yaml
collections:
  foundation:
    source: git+https://github.com/org/profiles.git@v1.0.0
```

**Process**:
1. Read collection source refs from `collections.yaml`
2. Resolve refs by cloning git repos → `cache/git/<commit-hash>/`
3. Find `profile.md` files in resolved collections
4. Copy to `share/profiles/<collection>/<profile>/profile.md`

**Output**: Profile specifications in known locations
```
share/profiles/foundation/base/profile.md
share/profiles/foundation/advanced/profile.md
```

**profile.md Format**: Markdown with YAML frontmatter
```markdown
---
profile:
  name: base
  version: 1.1.0
  description: Base configuration with core functionality
  extends: foundation  # Optional: inherit from another profile
  schema_version: 2

session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main
    config:
      extended_thinking: true
  context:
    module: context-simple
    source: git+https://github.com/microsoft/amplifier-module-context-simple@main
    config:
      max_tokens: 400000

providers:
- module: provider-anthropic
  source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
  config:
    default_model: claude-sonnet-4-5

tools:
- module: tool-web
  source: git+https://github.com/microsoft/amplifier-module-tool-web@main
- module: tool-issue
  source: git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection/modules/tool-issue

hooks:
- module: hooks-logging
  source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main

agents:
  explorer: https://raw.githubusercontent.com/payneio/lakehoused/refs/heads/main/registry/agents/foundation/explorer.md

context:
  foundation: git+https://github.com/payneio/lakehoused@main#subdirectory=registry/context/foundation

ui:
  show_thinking_stream: true
  show_tool_lines: 5
---

@foundation:context/shared/common-agent-base.md

# Base Profile
Description of the profile...
```

**Key Format Details:**
- **ONLY metadata** under `profile:` key (name, version, description, extends, schema_version)
- **All other config** at top level: `session:`, `providers:`, `tools:`, `hooks:`, `agents:`, `context:`, `ui:`
- **Module sources**:
  - Standalone repos: `git+https://github.com/{org}/{repo}@{ref}`
  - Subdirectories: `git+https://github.com/{org}/{repo}@{ref}#subdirectory=path`
- **Agent sources**: fsspec refs to markdown files (local, http, https supported)
- **Context sources**: fsspec refs or git refs with `#subdirectory=` for directories
- **Markdown body**: Can include @mentions for runtime context injection

---

### Phase 2: Resource Resolution

**Purpose**: Resolve all resource refs and organize by mount type

**Input**: `share/profiles/<collection>/<profile>/profile.md`

**Process**:
1. Parse profile.md YAML frontmatter
2. Extract resource references (orchestrator, context, providers, tools, hooks, agents)
3. Resolve each ref:
   - Git refs → `cache/git/<commit-hash>/<package-or-file>` (can contain subdirectory)
   - Fsspec refs → `cache/fsspec/<hash>/<package-or-file>` (local, http://, https:// supported)
4. Copy from cache to profile directory:
   - Modules → `<mount-type>/<profile-name>/` containing Python package
   - Agents → `agents/<name>.md` files
   - Context → `contexts/<context-name>/` directory (if present)

**Output**: Organized profile directory

**Directory Structure**:
```
share/profiles/foundation/base/
  profile.md                                   # Original specification
  profile.lock                                 # Change detection metadata

  orchestrator/                                # Mount type
    loop-streaming/                            # Profile name (resource directory)
      amplifier_module_loop_streaming/         # Python package (actual import)
        __init__.py
        orchestrator.py

  context/                                     # Mount type (NOTE: "context" not "context-manager")
    context-simple/                            # Profile name
      amplifier_module_context_simple/         # Python package
        __init__.py
        manager.py

  providers/                                   # Mount type
    provider-anthropic/                        # Profile name
      amplifier_module_provider_anthropic/     # Python package
        __init__.py
        provider.py

  tools/                                       # Mount type
    tool-web-search/                           # Profile name
      amplifier_module_tool_web_search/        # Python package
        __init__.py
        tool.py

  hooks/                                       # Mount type
    hook-logging/                              # Profile name
      amplifier_module_hook_logging/           # Python package
        __init__.py
        hook.py

  agents/                                      # App-layer data
    code-expert.md                             # Markdown file
    debug-helper.md

  contexts/                                    # App-layer context (NOT mounted, loaded via @mentions)
    docs/                                      # Context name
      USAGE.md
      subdir/
        EXTRA.md
```

**profile.lock Format** (for change detection):
```json
{
  "generated_at": "2025-11-28T10:30:00Z",
  "profile_hash": "abc123def456",
  "resources": {
    "orchestrator": {
      "name": "loop-streaming",
      "ref": "git+https://github.com/org/modules.git@abc123#amplifier_module_loop_streaming",
      "commit": "abc123def456789",
      "resolved_at": "2025-11-28T10:29:00Z"
    },
    "providers": [
      {
        "name": "provider-anthropic",
        "ref": "git+https://github.com/org/modules.git@abc123#amplifier_module_provider_anthropic",
        "commit": "abc123def456789",
        "resolved_at": "2025-11-28T10:29:00Z"
      }
    ],
    "agents": {
      "code-expert": {
        "ref": "git+https://github.com/org/agents.git@v1.0.0#experts/code.md",
        "commit": "fed456cba321",
        "resolved_at": "2025-11-28T10:29:00Z"
      }
    }
  }
}
```

---

### Phase 3: Mount Plan Generation

**Purpose**: Transform resolved profile into amplifier-core's expected format

**Input**: `share/profiles/<collection>/<profile>/` (complete directory)

**Process**:
1. Read profile.md for module configurations
2. Scan directory structure for resolved resources
3. Generate mount plan dict in STRING format (ecosystem standard)

**Output**: Mount plan dict ready for AmplifierSession

---

## Mount Plan Format

### Standard Format (Ecosystem Preference)

**Use STRING format with separate config sections:**

```python
{
    # Required: session resources
    "session": {
        "orchestrator": "loop-streaming",                              # String (profile name)
        "orchestrator_source": "file:///data/.lakehoused/share/profiles/foundation/base/orchestrator/loop-streaming",
        "context": "context-simple",                                   # String (profile name)
        "context_source": "file:///data/.lakehoused/share/profiles/foundation/base/context/context-simple"
    },

    # Optional: separate config sections
    "orchestrator": {
        "config": {
            "max_iterations": 10
        }
    },
    "context": {
        "config": {
            "max_tokens": 200000
        }
    },

    # Optional: list resources
    "providers": [
        {
            "module": "provider-anthropic",                            # String (profile name)
            "source": "file:///data/.lakehoused/share/profiles/foundation/base/providers/provider-anthropic",
            "config": {
                "model": "claude-3-5-sonnet-20241022",
                "api_key": "${ANTHROPIC_API_KEY}"
            }
        }
    ],
    "tools": [
        {
            "module": "tool-web-search",
            "source": "file:///data/.lakehoused/share/profiles/foundation/base/tools/tool-web-search",
            "config": {}
        }
    ],
    "hooks": [
        {
            "module": "hook-logging",
            "source": "file:///data/.lakehoused/share/profiles/foundation/base/hooks/hook-logging",
            "config": {
                "level": "INFO"
            }
        }
    ],

    # Optional: app-layer data (NOT mounted as modules)
    "agents": {
        "code-expert": {
            "content": "You are an expert software engineer...",
            "metadata": {
                "source": "git+https://github.com/org/agents.git@v1.0.0#experts/code.md"
            }
        }
    }
}
```

**Key Points**:
- Session resources use string format (not dict)
- Config goes in separate top-level keys (`orchestrator`, `context`)
- Source paths point to share directory (not cache)
- Source paths are `file://` URLs to local directories
- Agents are embedded content, not module references

---

## Validation Rules

### Required Fields

From `amplifier-core/amplifier_core/session.py:55-61`:

1. **config dict must exist**
   - Empty config → ValueError

2. **session.orchestrator must exist**
   - Missing → ValueError

3. **session.context must exist**
   - Missing → ValueError

4. **At least one provider required**
   - No providers → RuntimeError when executing
   - Validation comment: "At least one provider must be configured (required for agent loops)"

### Optional Fields

- `tools`: Defaults to `[]`
- `hooks`: Defaults to `[]`
- `agents`: Defaults to `{}`
- Missing `module` key in list items → Silent skip with warning

### Module Loading Behavior

From `amplifier-core/amplifier_core/session.py:157-208`:

- **Orchestrator/context failure**: Fatal, raises RuntimeError
- **Provider/tool/hook failure**: Warning logged, continues loading
- **Missing source**: Falls back to entry point resolution
- **Missing config**: Defaults to `{}`

---

## Module Resolution Contract

### ModuleLoader Behavior

1. **Receives**: `module_id="loop-streaming"`, `source="file:///.../loop-streaming"`
2. **Adds source to sys.path**: Makes directory importable
3. **Converts name**: `"loop-streaming"` → `"amplifier_module_loop_streaming"`
4. **Imports**: `import amplifier_module_loop_streaming`

### Directory Structure Contract

```
share/profiles/foundation/base/orchestrator/
  loop-streaming/                              ← sys.path addition point
    amplifier_module_loop_streaming/           ← Python package
      __init__.py                              ← Entry point
      orchestrator.py                          ← Implementation
```

The `source` path in mount plans points to the resource directory (e.g., `.../loop-streaming`), which contains the Python package with its full name.

---
