# Amplifierd Overview

**Understanding the big picture**

---

## The Problem

You want to use Amplifier (the AI agent system) for different workflows:
- **Coding**: Need code-focused agents, development tools, GitHub integration
- **Research**: Need web search, knowledge synthesis, citation management
- **Writing**: Need writing assistants, style guides, grammar checking

Each workflow needs different:
- AI models and providers
- Tools and capabilities
- Agent personas and instructions
- Context and memory settings

**Without profiles**: You'd configure all of this manually for every session. Tedious and error-prone.

---

## The Solution: Profiles

A **profile** is a reusable configuration template that defines everything a session needs.

**Write once, use many times:**
```yaml
---
session:
  orchestrator:
    module: loop-streaming     # How the agent executes
  context:
    module: context-simple     # How it manages memory
providers:
- module: provider-anthropic   # Which AI models
tools:
- module: tool-web            # What capabilities
- module: tool-github
agents:
  code-expert: https://...    # Which AI personas
---
```

**Use it:**
```bash
# Start session with this profile
POST /sessions {"profile_name": "foundation/coding"}
```

---

## Three Key Concepts

### 1. Profiles (What You Write)

**User-facing templates** in markdown with YAML frontmatter.

**You define:**
- Which modules to load (orchestrator, context, providers, tools, hooks)
- Configurations for each module
- Agent personas (markdown content)
- References to external resources (git repos, files)

**Location:** `registry/profiles/{collection}/{profile}.md`

**Example:** `foundation/base` profile for general-purpose use

### 2. Collections (How Profiles are Organized)

**Groups of related profiles** that can be shared and versioned.

**Defined in:** `.lakehoused/share/collections.yaml`

```yaml
collections:
  foundation:
    source: git+https://github.com/org/profiles.git@v1.0.0
  custom:
    source: /path/to/local/profiles/
```

**Why collections?**
- Share profiles across teams (via git)
- Version control (tag releases)
- Organize by purpose (foundation, development, production)

### 3. Mount Plans (What Amplifier-Core Uses)

**Runtime configuration format** that amplifier-core understands.

**Generated from profiles** when you create a session.

**Contains:**
- Module IDs (not filesystem paths)
- Profile hints for module resolution
- Embedded agent content
- Module configurations

**Example:**
```json
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "foundation/base",  // Profile hint!
      "config": {...}
    }
  }
}
```

---

## The Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. COLLECTIONS                                              │
│    collections.yaml                                         │
│    └─> git+https://github.com/org/profiles@v1.0.0          │
└──────────────────┬──────────────────────────────────────────┘
                   │ (clone & cache)
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PROFILES                                                 │
│    registry/profiles/foundation/base.md                     │
│    └─> YAML: session, providers, tools, agents...          │
└──────────────────┬──────────────────────────────────────────┘
                   │ (compile: resolve refs, organize)
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. COMPILED RESOURCES                                       │
│    .lakehoused/share/profiles/foundation/base/              │
│    ├─> orchestrator/loop-streaming/                         │
│    ├─> providers/provider-anthropic/                        │
│    ├─> tools/tool-web/                                      │
│    └─> agents/code-expert.md                                │
└──────────────────┬──────────────────────────────────────────┘
                   │ (generate mount plan)
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. MOUNT PLAN                                               │
│    {"session": {"orchestrator": {...}}, "providers": [...]} │
│    └─> Module IDs + "foundation/base" hints                 │
└──────────────────┬──────────────────────────────────────────┘
                   │ (resolver: hints → paths)
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. RUNNING SESSION                                          │
│    AmplifierSession initialized with loaded modules         │
│    └─> Ready to execute prompts!                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Principles

### 1. Separation of Concerns

**Profiles**: What you want (declarative)
**Mount plans**: How to load it (execution format)
**Resolver**: Where to find modules (runtime translation)

Each layer has one clear responsibility.

### 2. Portable by Design

Mount plans don't contain absolute paths - they contain:
- Module IDs: `"loop-streaming"`
- Profile hints: `"foundation/base"`

The **DaemonModuleSourceResolver** translates these to paths at runtime.

**Why?**
- Mount plans work across systems
- Share directory can be relocated
- Easier to test and version

### 3. Caching for Performance

Resources are cached to avoid repeated downloads:
- Git repos: `.lakehoused/cache/git/{commit-hash}/`
- Compiled profiles: `.lakehoused/share/profiles/{collection}/{profile}/`

**Change detection** via `profile.lock` ensures we only recompile when needed.

---

## Mental Model: Docker Compose

If you're familiar with Docker Compose, profiles work similarly:

```yaml
# docker-compose.yml       |  # profile.md
services:                   |  session:
  web:                      |    orchestrator:
    image: nginx:latest     |      module: loop-streaming
  db:                       |  providers:
    image: postgres:15      |  - module: provider-anthropic
```

**Docker Compose**: defines containers to run
**Amplifierd Profile**: defines modules to load

Both are declarative templates for runtime configuration.

---

## What Makes Amplifierd Special?

**Traditional approach:**
- Manual configuration per session
- Hardcoded paths and settings
- No reusability or sharing

**Amplifierd approach:**
- Declarative profiles (what, not how)
- Git-based sharing and versioning
- Automatic resource resolution
- Clean separation: definition vs. execution

---

## Common Workflow

**1. Choose or create a profile**
```bash
# Use existing
profile_name="foundation/base"

# Or create new in registry/profiles/myteam/myprofile.md
```

**2. Ensure profile is compiled**
```bash
# Compilation happens automatically, but you can force it
POST /profiles/compile {"profile_id": "myteam/myprofile"}
```

**3. Create session with profile**
```bash
POST /sessions {"profile_name": "myteam/myprofile"}
```

**4. Session is ready!**
- All modules loaded according to profile
- Agent personas available
- Tools mounted and ready
- Execute prompts immediately

---

## Next Steps

**For new users:**
1. Read [Profiles](profiles.md) to understand profile structure
2. Read [Mount Plans](mount-plans.md) to understand runtime format
3. Try creating your first profile

**For implementers:**
1. Read [Profile Lifecycle](../04-advanced/profile-lifecycle.md) for complete technical flow
2. Understand caching and resolution strategies
3. Debug profile compilation issues

**For troubleshooting:**
- Check `.lakehoused/share/profiles/` for compiled resources
- Review mount plan in `.lakehoused/state/sessions/{id}/mount_plan.json`
- Enable debug logging to see resolution steps

---

## Architecture At a Glance

```
lakehoused (daemon)
├── Profile Management
│   ├── Read profiles from registry
│   ├── Resolve git/fsspec references
│   └── Compile to share directory
├── Mount Plan Generation
│   ├── Transform profile → dict
│   └── Embed agents, extract configs
└── Session Coordination
    ├── Generate mount plans
    ├── Mount resolver
    └── Initialize AmplifierSession

amplifier-core (library)
├── Module Loading
│   ├── Use resolver if provided
│   └── Fall back to entry points
├── Session Management
│   └── Coordinate orchestrator, context, providers, tools, hooks
└── Execution
    └── Run agent loops with provided modules
```

**The boundary:**
- **lakehoused** handles profiles and resource management (daemon concerns)
- **amplifier-core** handles execution and module loading (library concerns)
- **Mount plans** are the clean contract between them

---

## Key Files and Directories

```
registry/profiles/           # Profile definitions (source)
.lakehoused/
├── cache/
│   └── git/{hash}/         # Cached git repos
├── share/
│   ├── collections.yaml    # Collection sources
│   └── profiles/           # Compiled profiles
│       └── {collection}/{profile}/
│           ├── orchestrator/
│           ├── providers/
│           ├── tools/
│           ├── hooks/
│           └── agents/
└── state/
    └── sessions/{id}/
        └── mount_plan.json # Generated mount plan
```

---

## Philosophy

Amplifierd follows the **ruthless simplicity** principle:

- Profiles are just markdown + YAML (no complex formats)
- Mount plans are plain dicts (no custom types)
- Resolution happens at runtime (no baked-in paths)
- Caching is transparent (users don't manage it)

**Design goal**: "It just works" while remaining transparent and debuggable.

---

**Ready to dive deeper?** Continue to [01-concepts/overview.md](01-concepts/overview.md) →
