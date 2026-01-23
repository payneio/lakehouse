# Profile Lifecycle (Legacy)

> **⚠️ DEPRECATED**: The profile compilation system has been replaced by the simpler **bundle system**.
> See [Bundles](../01-concepts/bundles.md) for the current approach.
>
> This documentation is preserved for historical reference only.

**Complete transformation from profile definition to running session**

---

## Overview

A profile goes through four distinct phases before becoming a running session. Each phase produces intermediate artifacts that enable caching, debugging, and optimization.

```
Phase 1: Discovery      → Profile specs located
Phase 2: Compilation    → Modules cached and organized
Phase 3: Mount Plan Gen → Runtime config created
Phase 4: Initialization → Session starts with loaded modules
```

---

## Phase 1: Collection Discovery

**Purpose**: Locate profile specifications from configured collections

**Input**: `.amplifierd/share/collections.yaml`
```yaml
collections:
  foundation:
    source: git+https://github.com/org/profiles.git@v1.0.0
  local:
    source: /path/to/local/profiles/
```

**Process**:
1. Read collection source references
2. Resolve each source:
   - Git refs → Clone to `cache/git/{commit-hash}/`
   - Local paths → Use directly
3. Scan for `profile.md` files in resolved sources
4. Copy profile specs to registry

**Output**: Profile specifications in known locations
```
registry/profiles/
├── foundation/
│   ├── base.md
│   ├── dev.md
│   └── production.md
└── local/
    └── custom.md
```

**Artifacts Created**:
- `cache/git/{commit-hash}/` - Cloned git repositories
- `registry/profiles/{collection}/{profile}.md` - Profile specifications

---

## Phase 2: Profile Compilation

**Purpose**: Resolve resource references and organize modules by type

**Input**: `registry/profiles/{collection}/{profile}.md`
```yaml
---
session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/org/modules@v1.0.0
providers:
- module: provider-anthropic
  source: git+https://github.com/org/modules@v1.0.0
agents:
  code-expert: https://example.com/code.md
---
```

**Process**:

1. **Parse profile frontmatter**:
   ```python
   frontmatter = parse_yaml_frontmatter(profile_path)
   session = frontmatter["session"]
   providers = frontmatter.get("providers", [])
   # ...
   ```

2. **Resolve resource references**:
   ```python
   # Git refs
   git+https://github.com/org/modules@v1.0.0
       ↓ (clone if not cached)
   cache/git/{commit-hash}/amplifier_module_loop_streaming/

   # HTTP refs (for agents)
   https://example.com/code.md
       ↓ (download if not cached)
   cache/fsspec/{hash}/code.md
   ```

3. **Organize by mount type**:
   ```python
   # Determine mount type from module ID
   "loop-streaming" → orchestrator/
   "provider-anthropic" → providers/
   "tool-web" → tools/
   ```

4. **Copy to profile directory**:
   ```
   share/profiles/foundation/base/
   ├── orchestrator/
   │   └── loop-streaming/
   │       └── amplifier_module_loop_streaming/
   ├── providers/
   │   └── provider-anthropic/
   │       └── amplifier_module_provider_anthropic/
   ├── agents/
   │   └── code-expert.md
   └── contexts/
       └── docs/
   ```

**Output**: Organized profile directory ready for use

**Artifacts Created**:
- `share/profiles/{collection}/{profile}/` - Organized module directories
- `share/profiles/{collection}/{profile}/profile.lock` - Change detection metadata

---

## Phase 3: Mount Plan Generation

**Purpose**: Transform profile into amplifier-core's expected format

**Input**: Compiled profile directory + `registry/profiles/{collection}/{profile}.md`

**Process**:

1. **Read profile frontmatter**:
   ```python
   profile_path = Path(f"registry/profiles/{collection}/{profile}.md")
   frontmatter = parse_yaml_frontmatter(profile_path)
   ```

2. **Extract module configurations**:
   ```python
   mount_plan = {
       "session": {
           "orchestrator": {
               "module": frontmatter["session"]["orchestrator"]["module"],
               "source": f"{collection}/{profile}",  # Profile hint!
               "config": frontmatter["session"]["orchestrator"].get("config", {})
           },
           "context": {
               "module": frontmatter["session"]["context"]["module"],
               "source": f"{collection}/{profile}",
               "config": frontmatter["session"]["context"].get("config", {})
           }
       }
   }
   ```

3. **Build provider/tool/hook arrays**:
   ```python
   mount_plan["providers"] = [
       {
           "module": p["module"],
           "source": f"{collection}/{profile}",
           "config": p.get("config", {})
       }
       for p in frontmatter.get("providers", [])
   ]
   ```

4. **Load and embed agent content**:
   ```python
   mount_plan["agents"] = {}
   agents_dir = profile_dir / "agents"
   for agent_file in agents_dir.glob("*.md"):
       name = agent_file.stem
       content = agent_file.read_text()
       mount_plan["agents"][name] = {
           "content": content,
           "metadata": {"source": f"{collection}:agents/{name}.md"}
       }
   ```

**Output**: Mount plan dict ready for AmplifierSession

**Artifacts Created**:
- `state/sessions/{session_id}/mount_plan.json` - Executable configuration

---

## Phase 4: Session Initialization

**Purpose**: Load modules and create running session

**Input**: Mount plan dict

**Process**:

1. **Create AmplifierSession**:
   ```python
   session = AmplifierSession(config=mount_plan, session_id=session_id)
   ```

2. **Mount module resolver**:
   ```python
   resolver = DaemonModuleSourceResolver(share_dir)
   await session.coordinator.mount("module-source-resolver", resolver)
   ```

3. **Initialize session** (loads all modules):
   ```python
   await session.initialize()
   ```

4. **Module loading** (happens inside initialize()):
   ```python
   # For orchestrator:
   module_id = "loop-streaming"
   source_hint = "foundation/base"

   # Resolver translates:
   path = resolver.resolve(module_id, source_hint)
   # → .amplifierd/share/profiles/foundation/base/orchestrator/loop-streaming/

   # Loader imports:
   sys.path.insert(0, str(path))
   import amplifier_module_loop_streaming

   # Mounts in coordinator:
   await amplifier_module_loop_streaming.mount(coordinator, config)
   ```

**Output**: Running AmplifierSession with all modules loaded

---

## Complete Flow with Artifacts

```
USER ACTION: Create session with "foundation/base"
    ↓
┌─────────────────────────────────────────────┐
│ PHASE 1: Discovery                          │
│ Input:  collections.yaml                    │
│ Output: registry/profiles/foundation/       │
│         ├── base.md                         │
│         ├── dev.md                          │
│         └── production.md                   │
│ Cache:  cache/git/{hash}/                   │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│ PHASE 2: Compilation                        │
│ Input:  registry/profiles/foundation/base.md│
│ Output: share/profiles/foundation/base/     │
│         ├── orchestrator/loop-streaming/    │
│         ├── providers/provider-anthropic/   │
│         ├── tools/tool-web/                 │
│         ├── hooks/hooks-logging/            │
│         └── agents/code-expert.md           │
│ Cache:  cache/git/{module-hashes}/          │
│ Meta:   profile.lock (change detection)     │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│ PHASE 3: Mount Plan Generation              │
│ Input:  Compiled profile + frontmatter      │
│ Output: state/sessions/{id}/mount_plan.json │
│ Format: {                                   │
│           "session": {                      │
│             "orchestrator": {               │
│               "module": "loop-streaming",   │
│               "source": "foundation/base",  │
│               "config": {...}               │
│             }                                │
│           },                                 │
│           "providers": [...],               │
│           "agents": {...}                   │
│         }                                    │
└────────────────┬────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────┐
│ PHASE 4: Session Initialization             │
│ 1. Create AmplifierSession(config)          │
│ 2. Mount DaemonModuleSourceResolver         │
│ 3. session.initialize()                     │
│    ├─> Resolve "foundation/base" → paths   │
│    ├─> Import Python packages              │
│    └─> Mount in coordinator                │
│ Output: Running session ready for prompts   │
└─────────────────────────────────────────────┘
```

---

## Change Detection

**Problem**: Recompiling profiles on every session creation is slow

**Solution**: `profile.lock` tracks compilation state

**Format**:
```json
{
  "generated_at": "2025-11-28T10:30:00Z",
  "profile_hash": "abc123def456",
  "resources": {
    "orchestrator": {
      "name": "loop-streaming",
      "ref": "git+https://github.com/org/modules@v1.0.0",
      "commit": "abc123def456789",
      "resolved_at": "2025-11-28T10:29:00Z"
    },
    "providers": [...]
  }
}
```

**How it works:**
1. After compilation, save resource metadata to `profile.lock`
2. On next compilation request:
   - Hash current `profile.md` content
   - Compare to `profile_hash` in lock file
   - If same → Skip compilation
   - If different → Recompile and update lock

**Benefits:**
- Fast session creation (no redundant compilation)
- Explicit cache invalidation (delete profile.lock to force recompile)
- Audit trail (know exactly what was compiled when)

---

## Caching Strategy

**Git repositories** (expensive to clone):
```
cache/git/{commit-hash}/
└── {module-or-collection}/
```

**Why commit hash?**
- Immutable: Same hash always has same content
- Shareable: Multiple profiles can reference same hash
- Deduplication: Clone once, use many times

**Compiled profiles** (expensive to organize):
```
share/profiles/{collection}/{profile}/
├── {mount-type}/{module-id}/
└── profile.lock
```

**Why cache these?**
- Module organization is expensive (copy operations)
- Change detection prevents redundant work
- Fast session creation (already organized)

**Cache locations:**
```
.amplifierd/
├── cache/
│   ├── git/{hash}/          # Cloned repos
│   └── fsspec/{hash}/       # Downloaded files
└── share/
    └── profiles/{}/{}/      # Compiled profiles
```

---

## Performance Considerations

**First session with new profile:**
```
1. Clone git repos          → ~5-30 seconds (network)
2. Compile profile         → ~1-2 seconds (filesystem)
3. Generate mount plan     → ~100ms (YAML parsing)
4. Initialize session      → ~200ms (module loading)
Total: ~6-32 seconds
```

**Subsequent sessions (cached):**
```
1. Check profile.lock      → ~10ms (hash comparison)
2. Skip compilation        → 0ms (cache hit)
3. Generate mount plan     → ~100ms
4. Initialize session      → ~200ms
Total: ~310ms
```

**Cache hit rate matters!** Optimize by:
- Pinning git refs (tags, commits) not branches
- Versioning collections
- Avoiding frequent profile edits

---

## Resolution Algorithm

**DaemonModuleSourceResolver** translates module IDs to paths:

**Input**:
- Module ID: `"provider-anthropic"`
- Profile hint: `"foundation/base"` or `{"collection": "foundation", "profile": "base"}`

**Steps**:

1. **Parse profile hint**:
   ```python
   if isinstance(hint, str):
       collection, profile = hint.split("/")
   else:
       collection = hint["collection"]
       profile = hint["profile"]
   ```

2. **Detect mount type from module ID**:
   ```python
   # Pattern matching:
   "provider-*" → providers/
   "tool-*" → tools/
   "hook-*" → hooks/
   "loop-*" or "orchestrator-*" → orchestrator/
   "context-*" → context/
   ```

3. **Build path**:
   ```python
   path = share_dir / "profiles" / collection / profile / mount_type / module_id
   # Example:
   # .amplifierd/share/profiles/foundation/base/providers/provider-anthropic/
   ```

4. **Return ModuleSource**:
   ```python
   return ModuleSource(path=path, module_id=module_id)
   ```

**Then ModuleLoader**:
```python
# Get filesystem path
module_path = source.resolve()

# Add to sys.path
sys.path.insert(0, str(module_path))

# Convert ID to package name
package_name = f"amplifier_module_{module_id.replace('-', '_')}"
# "provider-anthropic" → "amplifier_module_provider_anthropic"

# Import
module = importlib.import_module(package_name)

# Mount
await module.mount(coordinator, config)
```

---

## Intermediate Artifacts

### 1. Git Cache

**Location**: `.amplifierd/cache/git/{commit-hash}/`

**What**: Cloned git repositories

**Example**:
```
cache/git/abc123def456/
├── amplifier_module_loop_streaming/
│   ├── __init__.py
│   └── orchestrator.py
├── amplifier_module_provider_anthropic/
│   ├── __init__.py
│   └── provider.py
└── README.md
```

**Lifetime**: Permanent (unless manually cleared)

**Purpose**:
- Avoid repeated cloning
- Enable offline work (after first clone)
- Deduplication across profiles

### 2. Registry

**Location**: `registry/profiles/{collection}/{profile}.md`

**What**: Profile source specifications

**Example**:
```
registry/profiles/foundation/base.md
```

**Lifetime**: Permanent (version controlled)

**Purpose**:
- Source of truth for profile definitions
- Version control friendly
- Human-editable

### 3. Compiled Profile Directory

**Location**: `.amplifierd/share/profiles/{collection}/{profile}/`

**What**: Organized modules ready for loading

**Structure**:
```
share/profiles/foundation/base/
├── profile.md                          # Copy of source
├── profile.lock                        # Change detection
├── orchestrator/
│   └── loop-streaming/
│       └── amplifier_module_loop_streaming/
├── context/
│   └── context-simple/
│       └── amplifier_module_context_simple/
├── providers/
│   └── provider-anthropic/
│       └── amplifier_module_provider_anthropic/
├── tools/
│   ├── tool-web/
│   │   └── amplifier_module_tool_web/
│   └── tool-filesystem/
│       └── amplifier_module_tool_filesystem/
├── hooks/
│   └── hooks-logging/
│       └── amplifier_module_hooks_logging/
├── agents/
│   ├── code-expert.md
│   └── debug-helper.md
└── contexts/
    └── docs/
        ├── USAGE.md
        └── API.md
```

**Lifetime**: Until profile changes or manual cleanup

**Purpose**:
- Fast module discovery (organized by type)
- Resolver can find modules easily
- Change detection via profile.lock

### 4. Profile Lock

**Location**: `.amplifierd/share/profiles/{collection}/{profile}/profile.lock`

**What**: Compilation metadata for change detection

**Format**:
```json
{
  "generated_at": "2025-11-28T10:30:00Z",
  "profile_hash": "sha256:abc123...",
  "resources": {
    "orchestrator": {
      "name": "loop-streaming",
      "ref": "git+https://github.com/org/modules@v1.0.0",
      "commit": "abc123def456",
      "resolved_at": "2025-11-28T10:29:00Z"
    },
    "providers": [
      {
        "name": "provider-anthropic",
        "ref": "git+https://github.com/org/modules@v1.0.0",
        "commit": "abc123def456",
        "resolved_at": "2025-11-28T10:29:00Z"
      }
    ]
  }
}
```

**Lifetime**: Until profile changes

**Purpose**:
- Skip compilation if profile unchanged
- Audit: Know what was compiled when
- Debug: Verify resource versions

### 5. Mount Plan

**Location**: `.amplifierd/state/sessions/{session_id}/mount_plan.json`

**What**: Runtime configuration for AmplifierSession

**Format**:
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
      "config": {"max_tokens": 400000}
    }
  },
  "providers": [...],
  "tools": [...],
  "hooks": [...],
  "agents": {...}
}
```

**Lifetime**: Until session deleted

**Purpose**:
- Session initialization
- Resume capability
- Debugging (inspect exact config)

---

## Directory Structure Contract

**The resolver expects this layout:**

```
share/profiles/{collection}/{profile}/{mount_type}/{module_id}/
    └── amplifier_module_{module_id_underscored}/
        └── __init__.py
```

**Example**:
```
share/profiles/foundation/base/providers/provider-anthropic/
    └── amplifier_module_provider_anthropic/
        ├── __init__.py
        └── provider.py
```

**Two-level structure:**
1. **Resource directory** (`provider-anthropic/`): Profile-name format
   - What resolver returns
   - Organizational level
2. **Python package** (`amplifier_module_provider_anthropic/`): Package-name format
   - What Python imports
   - Actual module code

**Why two levels?**
- **Profile names**: User-friendly (hyphenated)
- **Package names**: Python-compatible (underscored)
- **Resolver**: Returns outer directory
- **Loader**: Imports inner package

---

## Compilation Triggers

**Automatic compilation:**
- Creating first session with a profile
- Profile changed (detected via hash comparison)

**Manual compilation:**
```bash
POST /profiles/compile
{
  "profile_id": "foundation/base",
  "force": true
}
```

**Force recompilation when:**
- Profile.lock corrupted
- Git cache issues
- Module sources updated
- Debugging compilation problems

---

## Module Identity Through Phases

**Module identity is preserved throughout:**

```
Phase 1-2: Git URL
git+https://github.com/org/modules@v1.0.0#subdirectory=amplifier_module_provider_anthropic
    ↓ (clone & cache)

Phase 2: Profile names modules
providers/provider-anthropic/amplifier_module_provider_anthropic/
    ↓ (generate mount plan)

Phase 3: Profile hint + module ID
{"module": "provider-anthropic", "source": "foundation/base"}
    ↓ (resolve)

Phase 4: Filesystem path
.amplifierd/share/profiles/foundation/base/providers/provider-anthropic/
    ↓ (import)

Runtime: Python package
import amplifier_module_provider_anthropic
```

**Three forms of identity:**
1. **Profile name** (hyphenated): `provider-anthropic` - User-facing
2. **Package name** (underscored): `amplifier_module_provider_anthropic` - Python
3. **Mount type** (organizational): `providers/` - Directory category

---

## Error Handling

**Phase 1 errors (discovery):**
- Git clone fails → Network issue, check connectivity
- Profile not found → Check collections.yaml source refs

**Phase 2 errors (compilation):**
- Resource ref invalid → Check git URLs, verify repos exist
- Module not found in repo → Verify subdirectory path

**Phase 3 errors (mount plan generation):**
- Missing required field → Check profile.md has session.orchestrator and session.context
- Invalid YAML → Check frontmatter syntax

**Phase 4 errors (initialization):**
- Module not found → Check compiled profile directory exists
- Import error → Check module's Python dependencies installed
- Mount error → Check module's mount() function signature

---

## Troubleshooting Guide

### Profile Won't Compile

**Symptom**: Compilation fails or hangs

**Check**:
1. Git URLs are accessible: `git ls-remote {url}`
2. Commits/tags exist: `git ls-remote --tags {url}`
3. Subdirectories correct: Clone manually and verify structure

**Debug**:
```bash
# Force recompilation with logging
POST /profiles/compile
{
  "profile_id": "foundation/base",
  "force": true
}

# Check compilation artifacts
ls -la .amplifierd/share/profiles/foundation/base/
```

### Session Won't Initialize

**Symptom**: Session creation succeeds but execution fails

**Check**:
1. Mount plan exists: `cat .amplifierd/state/sessions/{id}/mount_plan.json`
2. Modules compiled: `ls .amplifierd/share/profiles/{collection}/{profile}/`
3. Module structure: Each module has `amplifier_module_*/` directory

**Debug**:
```bash
# Check what the resolver would find
python3 -c "
from amplifierd.module_resolver import DaemonModuleSourceResolver
from pathlib import Path

resolver = DaemonModuleSourceResolver(Path('.amplifierd/share'))
source = resolver.resolve('provider-anthropic', 'foundation/base')
print(source.resolve())
"
```

### Module Not Loading

**Symptom**: "Module 'xxx' not found" during initialization

**Check**:
1. Module directory exists
2. Python package exists inside
3. Package has `__init__.py`
4. Package has `mount()` function

**Example verification**:
```bash
# Expected structure:
ls .amplifierd/share/profiles/foundation/base/providers/provider-anthropic/
# Should show: amplifier_module_provider_anthropic/

ls .amplifierd/share/profiles/foundation/base/providers/provider-anthropic/amplifier_module_provider_anthropic/
# Should show: __init__.py, provider.py, etc.

# Check for mount function:
grep -r "def mount" .amplifierd/share/profiles/foundation/base/providers/provider-anthropic/
```

---

## Cache Management

**View cache:**
```bash
# Git cache
ls -la .amplifierd/cache/git/

# Compiled profiles
ls -la .amplifierd/share/profiles/
```

**Clear cache:**
```bash
# Clear specific profile
rm -rf .amplifierd/share/profiles/foundation/base/

# Clear all git cache
rm -rf .amplifierd/cache/git/

# Force full rebuild
rm -rf .amplifierd/cache/ .amplifierd/share/profiles/
```

**Cache size:**
- Git cache grows with unique commits referenced
- Profile cache grows with unique profiles used
- Expect ~10-50MB per profile (depending on modules)

---

## Next Steps

**Understand module naming:**
- Read [Module Naming](../03-reference/module-naming.md)

**Create custom modules:**
- Read [Custom Modules](custom-modules.md)

**Debug issues:**
- Refer to troubleshooting sections above
- Enable debug logging: Set `LOG_LEVEL=DEBUG`
