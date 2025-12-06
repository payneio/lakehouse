# Amplifier Profiles Guide

**Comprehensive technical guide for developers working with Amplifier profiles**

---

## Table of Contents

1. [What Are Profiles?](#what-are-profiles)
2. [How Profiles Work](#how-profiles-work)
3. [Available Profiles](#available-profiles)
4. [Profile Structure](#profile-structure)
5. [Using Profiles](#using-profiles)
6. [Creating Custom Profiles](#creating-custom-profiles)
7. [Profile Resolution](#profile-resolution)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Profiles?

**Profiles** are reusable configuration bundles that define how Amplifier sessions operate. They specify:

- Which LLM provider and model to use
- Which orchestrator (execution strategy) to use
- Which context manager (memory strategy) to use
- Which tools, hooks, and agents are available
- System instructions for the AI assistant
- Resource limits and auto-compaction settings

###Key Characteristics

- **Format**: YAML frontmatter + Markdown body (`.md` files)
- **Inheritance**: Support single inheritance via `extends` field
- **Discoverable**: From multiple search paths (bundled, user, project)
- **Collection-aware**: Can reference `collection:name` syntax
- **Mergeable**: Child profiles can be partial (only specify differences)

### Philosophy

Profiles embody the "policy at edges" principle:
- **App layer decides**: Which modules, what configuration
- **Kernel executes**: Loads and coordinates modules
- **Profiles are the bridge**: Translate intent into mount plans

---

## How Profiles Work

### The Profile Lifecycle

```
┌─────────────────────┐
│  1. Discovery       │  Search paths for profile files
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Loading         │  Parse YAML + markdown, follow inheritance
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. Merging         │  Deep merge parent + child configs
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Compilation     │  Convert to mount plan (kernel contract)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Application     │  AmplifierSession uses mount plan
└─────────────────────┘
```

### Inheritance Chain Resolution

When you load a profile like `dev`, the system:

1. **Finds dev.md** (searches in priority order: project → user → bundled)
2. **Checks for `extends`** field (e.g., `extends: foundation:base`)
3. **Recursively loads parent** (finds `base.md`, checks its `extends`)
4. **Builds chain**: `[foundation → base → dev]`
5. **Merges configs**: foundation merged into base, then dev merged in
6. **Returns fully resolved profile**

### Deep Merging Strategy

**Module Lists** (tools, hooks, providers):
- Merge by module ID (not replaced!)
- Config fields are added/overridden individually
- Sources inherited if not specified in child

**Example**:
```yaml
# Parent
tools:
  - module: tool-web
    source: git+https://...
    config:
      timeout: 30

# Child
tools:
  - module: tool-web
    config:
      follow_redirects: true
  - module: tool-bash
    source: git+https://...

# Result after merge:
# tools:
#   - module: tool-web
#     source: git+https://...  # Inherited!
#     config:
#       timeout: 30             # From parent
#       follow_redirects: true  # From child
#   - module: tool-bash         # Added by child
```

**Session/UI Config**:
- Recursive deep merge
- Child values override parent at every level
- Unspecified keys are inherited

---

## Available Profiles

### Foundation Collection (`foundation:*`)

Located in: `amplifier-app-cli/data/collections/foundation/profiles/`

| Profile | Purpose | Key Features |
|---------|---------|--------------|
| **foundation** | Absolute minimum | Basic orchestrator (loop-basic), simple context, just Anthropic provider |
| **base** | Core functionality | Streaming orchestrator, web/search/task/todo tools, observability hooks |
| **production** | Reliability-optimized | Persistent context, higher compact threshold (0.9), selective agents |
| **test** | Mock provider | Mock LLM for testing, basic orchestrator, test-specific agents |

### Developer-Expertise Collection (`developer-expertise:*`)

Located in: `amplifier-app-cli/data/collections/developer-expertise/profiles/`

| Profile | Purpose | Key Features |
|---------|---------|--------------|
| **dev** | Default development | Extends base, adds filesystem/bash tools, debug mode, thinking stream |
| **full** | Feature-complete | Extends dev, all available tools/hooks, maximum observability |

### System Default

**Default profile**: `developer-expertise:dev`

Defined in: `amplifier-app-cli/data/profiles/DEFAULTS.yaml`

---

## Profile Structure

### Complete YAML Schema

```yaml
---
profile:
  name: profile-identifier          # Required: unique ID
  version: "1.2.0"                   # Required: semantic version
  description: "Human readable"      # Required: purpose
  model: "provider/model"           # Optional: shorthand
  extends: base                      # Optional: parent profile

session:
  orchestrator:                      # Required
    module: loop-streaming           # Module ID
    source: git+https://...          # Git URL (inherited if omitted in child)
    config:                          # Optional: module-specific config
      extended_thinking: true
  context:                           # Required
    module: context-simple
    source: git+https://...
    config:
      max_tokens: 400000
      compact_threshold: 0.8
  injection_budget_per_turn: 200000  # Optional: max tokens per turn

task:                                 # Optional: task configuration
  max_recursion_depth: 1

ui:                                   # Optional: UI preferences
  show_thinking_stream: true
  show_tool_lines: 5

providers:                            # List of LLM providers
  - module: provider-anthropic
    source: git+https://...
    config:
      default_model: claude-sonnet-4-5
      debug: false

tools:                                # List of available tools
  - module: tool-filesystem
    source: git+https://...
  - module: tool-bash
    source: git+https://...
    config:
      allowed_commands: ["ls", "cat"]

hooks:                                # List of observability hooks
  - module: hooks-logging
    source: git+https://...
    config:
      mode: session-only
  - module: hooks-status-context
    config:
      include_git: true

agents:                               # Optional: agent discovery
  dirs: ["./agents"]                 # Directories to search
  include:                           # Filter to specific agents
    - zen-architect
    - bug-hunter
---

# Markdown body becomes system instruction (supports @mentions)
You are an Amplifier development assistant...

@.amplifier/context/standards.md
```

### Module Configuration Pattern

Every module (provider, tool, hook) follows this structure:

```yaml
- module: tool-id              # Required: identifies the module
  source: git+https://...      # Optional: URL to load from (inherited from parent)
  config:                       # Optional: module-specific settings
    key1: value1
    key2: value2
```

### Special Fields

- **`extends`**: Parent profile reference (simple name or `collection:profiles/path.md`)
- **`model`**: Shorthand for `providers.config.default_model`
- **`session.injection_budget_per_turn`**: Limits token injection per turn
- **`agents.dirs`**: Search paths for agent `.md` files
- **`agents.include`**: Whitelist of agents to load (others ignored)

---

## Using Profiles

### CLI Commands

```bash
# List all available profiles with status
amplifier profile list

# Show currently active profile and source
amplifier profile current

# Show detailed profile configuration (with inheritance chain)
amplifier profile show dev
amplifier profile show dev --detailed  # Shows all config values

# Set active profile (different scopes)
amplifier profile use dev              # Local only (just you)
amplifier profile use dev --local
amplifier profile use dev --project    # Project default (commit to .amplifier/settings.yaml)
amplifier profile use dev --global     # Global (user's ~/.amplifier/settings.yaml)

# Reset local profile to fallback to project default
amplifier profile reset

# Manage project default profile
amplifier profile default              # Show current
amplifier profile default --set base
amplifier profile default --clear
```

### Configuration Hierarchy

When no profile is explicitly set:

1. **Local settings** (`.amplifier/settings.local.yaml` - not committed)
2. **Project settings** (`.amplifier/settings.yaml` - committed)
3. **System default** (`developer-expertise:dev`)

### Programmatic API

```python
from amplifier_profiles import ProfileLoader, compile_profile_to_mount_plan
from amplifier_core import AmplifierSession
from pathlib import Path

# Step 1: Create loader with search paths
search_paths = [
    Path("amplifier_app_cli/data/profiles"),           # Bundled
    Path.home() / ".amplifier" / "profiles",           # User
    Path(".amplifier/profiles"),                       # Project
]
loader = ProfileLoader(search_paths=search_paths)

# Step 2: Discover profiles
profiles = loader.list_profiles()  # Returns ["foundation", "base", "dev", ...]

# Step 3: Load a profile (with inheritance resolved)
profile = loader.load_profile("dev")

# Step 4: Get inheritance chain for inspection
chain = loader.get_inheritance_chain("dev")
# Returns: ["foundation:profiles/foundation.md", "foundation:profiles/base.md", "dev"]

# Step 5: Compile to Mount Plan (ready for session)
mount_plan = compile_profile_to_mount_plan(profile, agent_loader=None)

# Step 6: Create and use session
async with AmplifierSession(config=mount_plan) as session:
    response = await session.execute("Hello!")
    print(response)
```

---

## Creating Custom Profiles

### Step 1: Choose a Parent Profile

Start by extending an existing profile rather than building from scratch:

```yaml
---
profile:
  name: my-dev
  version: 1.0.0
  description: My custom development profile
  extends: developer-expertise:dev  # Or foundation:base
```

### Step 2: Override Only What You Need

You only need to specify differences from the parent:

```yaml
# Override model
providers:
  - module: provider-anthropic
    config:
      default_model: claude-opus-4-1  # Use Opus instead of Sonnet

# Add project-specific tools
tools:
  - module: tool-internal-api
    source: git+https://github.com/yourorg/tool-internal-api@main
    config:
      endpoint: http://localhost:8000
```

### Step 3: Add Custom System Instructions

The markdown body becomes the system instruction:

```markdown
---
# ... yaml frontmatter above ...
---

You are an AI assistant for the XYZ project.

## Project Standards

@.amplifier/context/standards.md

## Project Architecture

@ARCHITECTURE.md
```

### Step 4: Save and Test

**Location options**:
- **Project**: `.amplifier/profiles/my-dev.md`
- **User**: `~/.amplifier/profiles/my-dev.md`

**Test**:
```bash
amplifier profile show my-dev          # Verify config
amplifier profile use my-dev --local   # Activate
amplifier run "test prompt"             # Try it out
```

### Complete Example

```yaml
# File: .amplifier/profiles/project-dev.md
---
profile:
  name: project-dev
  version: 1.0.0
  description: Our project's development profile
  extends: developer-expertise:dev

providers:
  - module: provider-anthropic
    config:
      default_model: claude-opus-4-1

tools:
  - module: tool-internal-api
    source: git+https://github.com/ourorg/tool-internal-api@main
    config:
      endpoint: http://localhost:8000

agents:
  dirs:
    - ./agents
    - ./project-agents  # Project-specific agents
  include:
    - zen-architect
    - project-reviewer
---

You are an AI assistant for the XYZ project.

## Project Context
@.amplifier/context/project-overview.md

## Coding Standards
@.amplifier/context/standards.md
```

---

## Profile Resolution

### Search Path Priority

Highest priority (overrides others):
1. Project local: `.amplifier/settings.local.yaml`
2. Project settings: `.amplifier/settings.yaml`
3. User settings: `~/.amplifier/settings.yaml`
4. Project profiles: `.amplifier/profiles/*.md`
5. User profiles: `~/.amplifier/profiles/*.md`
6. Collection profiles: `~/.amplifier/collections/<name>/profiles/`
7. Bundled profiles: `amplifier_app_cli/data/profiles/*.md`
8. Bundled collection profiles: `amplifier_app_cli/data/collections/<name>/profiles/`

Lowest priority (fallback)

### Inheritance Resolution Algorithm

```
Input: "dev"

1. Find dev profile file (reverse search order: project → user → bundled)
2. Load and parse dev.md
3. Check for "extends: foundation:base" field
   ├─ Find base profile in foundation collection
   ├─ Load and parse base.md
   ├─ Check for "extends: foundation:foundation" field
   │  ├─ Find foundation profile
   │  ├─ Load and parse
   │  └─ Check for extends: NO → Stop
   │  └─ Build chain: [foundation, base]
   └─ Add dev to chain: [foundation, base, dev]

4. Merge process:
   foundation config
     ↓ merge ↓
   base config (base values override foundation)
     ↓ merge ↓
   dev config (dev values override base)
     ↓
   Result: fully resolved config
```

### Source Inheritance

Key feature enabling DRY profiles:

```yaml
# foundation.md (root)
providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
    config:
      model: claude-sonnet-4-5

# dev.md (child - extends foundation indirectly via base)
providers:
  - module: provider-anthropic
    config:
      debug: true  # Override just this config key

# After merge, effective config is:
# providers:
#   - module: provider-anthropic
#     source: git+https://...  # Inherited from foundation!
#     config:
#       model: claude-sonnet-4-5  # From foundation
#       debug: true               # From dev
```

---

## Best Practices

### 1. Always Extend a Base Profile

**Don't**:
```yaml
profile:
  name: my-profile
  # No extends - must specify everything!
```

**Do**:
```yaml
profile:
  name: my-profile
  extends: developer-expertise:dev
  # Override only what's different
```

### 2. Use Collections for Reusable Profiles

If you have multiple projects with similar needs, create a collection:

```
my-collection/
├── profiles/
│   ├── base.md
│   └── production.md
└── agents/
    └── project-reviewer.md
```

### 3. Keep Custom Profiles Minimal

Only specify differences from the parent. This makes profiles:
- Easier to maintain
- Clearer in intent
- More resilient to upstream changes

### 4. Test Profile Changes

Before committing profile changes:

```bash
# Show merged config
amplifier profile show my-profile --detailed

# Test in single-shot mode
amplifier run --profile my-profile "test prompt"

# Test in interactive mode
amplifier run --profile my-profile --mode chat
```

### 5. Document Your Choices

In the markdown body, explain why you made specific configuration choices:

```markdown
---
# ... yaml frontmatter ...
---

You are a reviewer for the XYZ project.

## Configuration Notes

- Using Opus instead of Sonnet for higher quality reviews
- Disabled bash tool for security (review-only mode)
- Extended compact threshold to preserve more context
```

### 6. Version Your Profiles

Use semantic versioning and track changes:

```yaml
profile:
  name: project-dev
  version: 2.1.0  # Updated version
  description: Development profile (v2.1.0 - added internal-api tool)
```

---

## Troubleshooting

### Profile Not Found

**Error**: `Profile 'my-profile' not found`

**Check**:
1. Profile file exists in search paths
2. Filename matches profile name (case-sensitive)
3. `.md` extension present
4. YAML frontmatter is valid

**Debug**:
```bash
amplifier profile list              # See discovered profiles
amplifier profile show my-profile   # See resolution details
```

### Inheritance Chain Broken

**Error**: `Cannot resolve parent profile 'base'`

**Check**:
1. Parent profile name is correct (typos)
2. Collection reference uses correct syntax (`collection:path`)
3. Parent profile is in search paths

**Debug**:
```bash
# Show inheritance chain
amplifier profile show my-profile
# Look for "Extends: foundation:profiles/base.md"
```

### Module Not Loading

**Error**: `Failed to load module 'tool-xyz'`

**Check**:
1. `source` field is present (required for git distribution)
2. Git URL is correct and accessible
3. Module exports correct entry point
4. Module ID matches entry point name

**Debug**:
```bash
# Show full config
amplifier profile show my-profile --detailed

# Check module availability
amplifier module list
```

### Config Merge Not Working as Expected

**Issue**: Child config not overriding parent

**Check**:
1. Module IDs match exactly (case-sensitive)
2. Config keys are spelled correctly
3. Deep merge applies (nested dicts merge, not replace)

**Debug**:
```bash
# Show final merged config
amplifier profile show my-profile --detailed

# Compare with parent
amplifier profile show base --detailed
```

### @Mentions Not Resolving

**Issue**: Context files not loading

**Check**:
1. File paths are correct
2. Files exist at specified locations
3. Syntax is correct (`@path/to/file.md`)
4. Circular references avoided

**Debug**:
```bash
# Check compilation
amplifier profile show my-profile --detailed
# Look for resolved system instruction
```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| Bundled profiles | `amplifier-app-cli/amplifier_app_cli/data/profiles/` |
| Foundation collection | `amplifier-app-cli/amplifier_app_cli/data/collections/foundation/profiles/` |
| Developer-expertise collection | `amplifier-app-cli/amplifier_app_cli/data/collections/developer-expertise/profiles/` |
| User profiles | `~/.amplifier/profiles/` |
| Project profiles | `.amplifier/profiles/` |
| Local settings | `.amplifier/settings.local.yaml` |
| Project settings | `.amplifier/settings.yaml` |
| User settings | `~/.amplifier/settings.yaml` |

### Key Implementation Files

| File | Purpose |
|------|---------|
| `amplifier-profiles/src/amplifier_profiles/loader.py` | Profile loading & resolution |
| `amplifier-profiles/src/amplifier_profiles/merger.py` | Deep merge logic |
| `amplifier-profiles/src/amplifier_profiles/compiler.py` | Profile → mount plan compilation |
| `amplifier-profiles/src/amplifier_profiles/schema.py` | Pydantic schemas |
| `amplifier-app-cli/amplifier_app_cli/commands/profile.py` | CLI commands |

### Documentation

| Document | Purpose |
|----------|---------|
| `amplifier-profiles/docs/PROFILE_AUTHORING.md` | Complete user guide |
| `amplifier-profiles/docs/DESIGN.md` | Architecture docs |
| `amplifier-profiles/README.md` | API reference |

### Related Guides

- [**Modules Guide**](./modules.md) - Understanding Amplifier modules
- [**Mounts Guide**](./mounts.md) - How mount plans work
- [**CLI Guide**](./cli.md) - Using the Amplifier CLI
- [**Development Guide**](./development.md) - Development workflows and custom modules

---

## Quick Reference

### Common Commands

```bash
# List profiles
amplifier profile list

# Show profile
amplifier profile show dev

# Use profile
amplifier profile use dev

# Reset to project default
amplifier profile reset

# Create custom profile
# 1. Create .amplifier/profiles/my-profile.md
# 2. Add yaml frontmatter + markdown body
# 3. Test: amplifier profile show my-profile
# 4. Activate: amplifier profile use my-profile
```

### Profile Template

```yaml
---
profile:
  name: my-profile
  version: 1.0.0
  description: Description here
  extends: developer-expertise:dev

# Override providers/tools/hooks as needed
providers:
  - module: provider-anthropic
    config:
      default_model: claude-opus-4-1
---

System instruction goes here.

@.amplifier/context/project-context.md
```

### Inheritance Chain Visualization

```
foundation (minimal)
    ↓ extends
base (core tools + hooks)
    ↓ extends
dev (+ filesystem + bash)
    ↓ extends
my-profile (project-specific)
```

---

**For more information**, see the [Amplifier Profiles Documentation](../amplifier-profiles/docs/PROFILE_AUTHORING.md).
