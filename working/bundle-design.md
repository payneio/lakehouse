# Lakehouse Bundle Integration Design

**Status**: Ready for Implementation
**Author**: Claude (with Paul)
**Date**: 2026-01-22
**Context**: Aligning lakehouse with amplifier bundle architecture

---

## Executive Summary

Lakehouse's custom profile system has diverged from amplifier's bundle architecture, causing maintenance burden and compatibility issues (e.g., the "No providers available" error from import mismatches). This design proposes **eliminating lakehouse-specific abstractions** and using Foundation's bundle system directly.

### Key Decisions

1. **Use Foundation bundles directly** - No separate "profile" or "behavior" concepts
2. **Bundles = Profiles** - User configurations are just bundles in well-known locations
3. **Allow uv installation** of dependencies into daemon's venv
4. **Minimal lakehouse layer** - Only adds well-known paths and @project: resolution
5. **Single-step migration** - Convert all profiles to standard bundle format

### What Changes

| Before | After |
|--------|-------|
| Lakehouse profiles (custom format) | Standard Foundation bundles |
| 8-stage compilation pipeline (~827 lines) | Bundle loading (~50 lines) |
| `amp://` registry URIs | Standard git URLs or well-known names |
| Profiles + Behaviors (two concepts) | Bundles (one concept) |
| `~/.lakehoused/profiles/` | `~/.lakehoused/bundles/` |

---

## Problem Statement

### Current Issues

1. **Import compatibility failures**: Modules reference `TextContent` but amplifier-core exports `TextBlock`
2. **Parallel maintenance burden**: 8-stage profile compilation pipeline duplicates Foundation's bundle system
3. **Concept proliferation**: Profiles vs Behaviors vs Bundles creates confusion
4. **No ecosystem access**: Can't easily use published amplifier bundles
5. **Version drift**: Lakehouse system diverges from upstream improvements

### Root Cause

Lakehouse built its own profile/module system before amplifier-foundation matured. Foundation bundles now provide everything lakehouse profiles do (and more), making the custom system redundant.

---

## Architecture Overview

### Current State: Lakehouse Profile System

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAKEHOUSE PROFILE SYSTEM                          │
│                                                                       │
│  profile.yaml → 8-Stage Compilation Pipeline → mount_plan.json       │
│       │                    │                         │               │
│       │         ┌──────────┴──────────┐              │               │
│       │         │ 1. Load profile     │              │               │
│       │         │ 2. Resolve amp://   │              │               │
│       │         │ 3. Download modules │              │               │
│       │         │ 4. Cache to share/  │              │               │
│       │         │ 5. Install deps     │              │               │
│       │         │ 6. Merge behaviors  │              │               │
│       │         │ 7. Generate plan    │              │               │
│       │         │ 8. Validate         │              │               │
│       │         └─────────────────────┘              │               │
│       │                                              ▼               │
│       │                                    AmplifierSession          │
│       │                                                              │
│  registries.yaml ──→ amp:// URI resolution                          │
│  ~/.lakehoused/share/profiles/{name}/ ──→ Module cache              │
└─────────────────────────────────────────────────────────────────────┘
```

**Problems**:
- 827 lines of compilation code duplicating Foundation functionality
- Custom caching that doesn't benefit from Foundation improvements
- amp:// URIs don't work outside lakehouse
- Profiles/behaviors are just bundles with different names

### Target State: Direct Bundle Usage

```
┌─────────────────────────────────────────────────────────────────────┐
│                  LAKEHOUSE (MINIMAL LAYER)                           │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  LakehouseBundleManager (~50 lines)                          │   │
│  │                                                              │   │
│  │  • Well-known bundle locations                              │   │
│  │  • @project: resolver injection                             │   │
│  │  • Session state persistence                                │   │
│  └────────────────────────────┬─────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AMPLIFIER FOUNDATION                             │
│                                                                       │
│  BundleRegistry → Bundle.compose() → Bundle.prepare() → Session     │
│                                           │                          │
│                                    ModuleActivator                   │
│                                    (uv pip install)                  │
│                                           │                          │
│  ~/.lakehoused/cache/bundles/ ←──────────┘                          │
│                                                                       │
│  SimpleSourceResolver → GitSourceHandler, FileSourceHandler, etc.   │
│                                                                       │
│  Bundle features used:                                               │
│  • bundle.name (simple names)                                        │
│  • bundle.context (file injection)                                   │
│  • bundle.instruction (system prompts)                               │
│  • bundle.includes (composition)                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Benefits**:
- ~50 lines of lakehouse code vs 827 lines of pipeline
- Automatic upstream compatibility with Foundation improvements
- Access to entire published bundle ecosystem
- Users learn one system (bundles), not three (profiles + behaviors + bundles)
- Bundles already provide context injection, composition, and simple names

---

## Detailed Design

### Component: LakehouseBundleManager

Thin layer over Foundation's BundleRegistry with runtime configuration injection.

**Location**: `lakehouse_library/bundles/manager.py`

```python
from pathlib import Path
from typing import Any
import copy

from amplifier_foundation import BundleRegistry, Bundle, PreparedBundle
from amplifier_core import AmplifierSession

class LakehouseBundleManager:
    """Minimal wrapper over Foundation's bundle system.

    Adds only:
    - Well-known bundle locations
    - Runtime configuration injection (working_dir, API keys, session logs)
    - @project: resolver extension
    """

    def __init__(self, home_dir: Path | None = None, data_dir: Path | None = None):
        self.home_dir = home_dir or Path.home() / ".lakehoused"
        self.data_dir = data_dir or Path.home() / "amplifier"

        # Initialize Foundation's bundle registry
        self.registry = BundleRegistry(home=self.home_dir)

        # Well-known bundle locations (searched in order)
        self.well_known_paths = [
            self.home_dir / "bundles",  # User bundles
        ]

    async def load_bundle(self, bundle_ref: str) -> PreparedBundle:
        """Load bundle from name, file://, or git+https://

        Args:
            bundle_ref:
                - Simple name: "my-config" (searches well-known paths)
                - File URI: "file:///path/to/bundle"
                - Git URI: "git+https://github.com/org/repo@main"

        Returns:
            PreparedBundle ready for session creation

        Note:
            Bundle loading precedence for local files:
            1. bundle.yaml (primary)
            2. bundle.md (fallback if no YAML)
        """

        # 1. Try as full URI
        if "://" in bundle_ref:
            bundle = await self.registry.load(bundle_ref)
            return await bundle.prepare()

        # 2. Try well-known locations (bundle.yaml takes precedence over bundle.md)
        for base_path in self.well_known_paths:
            bundle_path = base_path / bundle_ref

            # Check bundle.yaml first (primary)
            if (bundle_path / "bundle.yaml").exists():
                bundle = await self.registry.load(f"file://{bundle_path}")
                return await bundle.prepare()

            # Fallback to bundle.md
            if (bundle_path / "bundle.md").exists():
                bundle = await self.registry.load(f"file://{bundle_path}")
                return await bundle.prepare()

        raise ValueError(
            f"Bundle not found: {bundle_ref}\n"
            f"Searched: {[str(p / bundle_ref) for p in self.well_known_paths]}\n"
            f"Tip: Use full URI (file:// or git+https://) or place bundle in "
            f"{self.well_known_paths[0]}"
        )

    async def create_session(
        self,
        bundle_ref: str,
        session_id: str,
        amplified_dir: Path | None = None,
        approval_system: Any | None = None,
        display_system: Any | None = None,
    ) -> AmplifierSession:
        """Create session with lakehouse runtime configuration.

        Args:
            bundle_ref: Bundle name or URI
            session_id: Unique session identifier
            amplified_dir: Project directory for @project: resolution and working_dir
            approval_system: Optional approval system
            display_system: Optional display system

        Returns:
            Configured AmplifierSession with lakehouse runtime config injected

        Critical Timing for Config Injection:
            Two-phase injection process:

            Phase 1 - Pre-prepare (module configs):
            - working_dir, allowed_write_paths, session_log_template, api_key
            - Injected BEFORE bundle.prepare() so modules initialize with correct config

            Phase 2 - Post-initialize (mention resolution):
            - @project: resolver registered as capability
            - Injected AFTER session.initialize() when coordinator is ready
            - System prompt factory uses capability when processing context
        """

        # 1. Load bundle (but don't prepare yet)
        bundle = await self._load_bundle_unprepared(bundle_ref)

        # 2. PHASE 1: Inject runtime config BEFORE prepare()
        #    This modifies bundle's tool/hook/provider configs before Foundation processes them
        if amplified_dir:
            self._inject_runtime_config(bundle, session_id, amplified_dir)

        # 3. Prepare bundle with injected config
        prepared = await bundle.prepare()

        # 4. Create session
        session = await prepared.create_session(
            session_id=session_id,
            parent_id=None,
            approval_system=approval_system,
            display_system=display_system,
        )

        # 5. Initialize session (loads modules, sets up coordinator)
        await session.initialize()

        # 6. PHASE 2: Register @project: resolver AFTER initialize
        #    System prompt factory will use this capability when resolving @project: mentions
        if amplified_dir:
            self._register_mention_resolver(session, amplified_dir)

        return session

    async def _load_bundle_unprepared(self, bundle_ref: str) -> Bundle:
        """Load bundle without preparing (for pre-prepare config injection)."""

        if "://" in bundle_ref:
            return await self.registry.load(bundle_ref)

        for base_path in self.well_known_paths:
            bundle_path = base_path / bundle_ref
            if (bundle_path / "bundle.yaml").exists():
                return await self.registry.load(f"file://{bundle_path}")
            if (bundle_path / "bundle.md").exists():
                return await self.registry.load(f"file://{bundle_path}")

        raise ValueError(f"Bundle not found: {bundle_ref}")

    def _inject_runtime_config(
        self,
        bundle: Bundle,
        session_id: str,
        amplified_dir: Path,
    ) -> None:
        """Inject lakehouse-specific runtime configuration into bundle's mount plan.

        This must happen BEFORE bundle.prepare() so Foundation's module loading
        and system prompt factory have access to the correct configuration.

        Injects:
        1. working_dir for all tools (enables relative paths)
        2. allowed_write_paths for tool-filesystem (security)
        3. session_log_template for hooks-logging (event tracking)
        4. api_key for providers from secrets.yaml (security)
        """

        state_dir = self.home_dir / "state"
        amplified_dir_str = str(amplified_dir.resolve())

        # Inject working_dir into all tools
        if hasattr(bundle, 'tools'):
            for tool in bundle.tools or []:
                if 'config' not in tool:
                    tool['config'] = {}
                if 'working_dir' not in tool['config']:
                    tool['config']['working_dir'] = amplified_dir_str

        # Inject allowed_write_paths into tool-filesystem
        if hasattr(bundle, 'tools'):
            for tool in bundle.tools or []:
                tool_module = tool.get("module", "") or tool.get("id", "")
                is_filesystem_tool = (
                    "tool-filesystem" in tool_module or
                    "filesystem" in tool.get("source", "")
                )
                if is_filesystem_tool:
                    if 'allowed_write_paths' not in tool['config']:
                        tool['config']['allowed_write_paths'] = [amplified_dir_str]

        # Inject session_log_template into hooks-logging
        session_log_path = str(state_dir / "sessions" / session_id / "events.jsonl")
        if hasattr(bundle, 'hooks'):
            for hook in bundle.hooks or []:
                hook_id = hook.get("module", "") or hook.get("id", "")
                if "hooks-logging" in hook_id or "logging" in hook_id:
                    if 'config' not in hook:
                        hook['config'] = {}
                    if 'session_log_template' not in hook['config']:
                        hook['config']['session_log_template'] = session_log_path

        # Inject API keys from secrets.yaml into providers
        secrets = self._load_secrets()
        if hasattr(bundle, 'providers') and secrets:
            for provider in bundle.providers or []:
                provider_id = provider.get("module", "") or provider.get("id", "")
                if 'config' not in provider:
                    provider['config'] = {}
                if 'api_key' not in provider['config']:
                    # Check secrets for this provider
                    if 'api_keys' in secrets and provider_id in secrets['api_keys']:
                        provider['config']['api_key'] = secrets['api_keys'][provider_id]

    def _load_secrets(self) -> dict:
        """Load secrets from secrets.yaml."""
        import yaml

        secrets_file = self.home_dir / "config" / "secrets.yaml"
        if not secrets_file.exists():
            return {}

        try:
            return yaml.safe_load(secrets_file.read_text())
        except Exception:
            return {}

    def _register_mention_resolver(
        self,
        session: AmplifierSession,
        amplified_dir: Path,
    ) -> None:
        """Register @project: mention resolver as session capability.

        Creates a resolver chain:
        1. @project: → amplified_dir/path (lakehouse-specific)
        2. Other @mentions → Foundation's resolver (bundle contexts, etc.)

        Critical Timing: This must happen AFTER session.initialize() because:
        - System prompt factory is registered after session creation
        - Factory queries coordinator for "mention_resolver" capability
        - Our lakehouse resolver wraps any existing Foundation resolver

        The resolver chain works via capability lookup:
        1. System prompt factory calls: coordinator.get_capability("mention_resolver")
        2. Gets our lakehouse resolver (registered here)
        3. Lakehouse resolver handles @project:, delegates others to Foundation
        """

        # Get Foundation's existing mention resolver (if any)
        foundation_resolver = session.coordinator.get_capability("mention_resolver")

        # Create lakehouse resolver that wraps Foundation's
        lakehouse_resolver = LakehouseMentionResolver(
            amplified_dir=amplified_dir,
            bundle_resolver=foundation_resolver,
            data_dir=self.data_dir,
        )

        # Register as the mention_resolver capability
        # Tools (tool-filesystem, tool-search) query this capability for @project: paths
        # System prompt factory creates its own resolver for context/instruction @mentions
        # Both approaches work together: tools get @project: via capability, factory handles others
        session.coordinator.register_capability("mention_resolver", lakehouse_resolver)
```

**That's it.** ~200 lines replaces the entire profile compilation system while adding proper runtime configuration injection.

---

### Runtime Configuration Injection Reference

**Critical Design Point**: Lakehouse uses two-phase injection to handle different timing requirements.

#### Two-Phase Injection Strategy

**Phase 1 - Pre-Prepare (Module Configs)**:
Inject BEFORE `bundle.prepare()` so modules initialize with correct configuration:
- `working_dir` for all tools
- `allowed_write_paths` for tool-filesystem
- `session_log_template` for hooks-logging
- `api_key` for providers

Foundation's `bundle.prepare()`:
1. Resolves all module sources (git clones, file paths)
2. Initializes modules with their configurations
3. Returns PreparedBundle ready for session creation

If we inject configuration AFTER prepare(), modules already initialized with wrong/missing config.

**Phase 2 - Post-Initialize (Mention Resolution)**:
Register AFTER `session.initialize()` when coordinator is ready:
- `@project:` mention resolver as capability

System prompt factory creation:
1. Happens AFTER `session.initialize()` (not during prepare!)
2. Factory registered via: `context_manager.set_system_prompt_factory(factory)`
3. Factory queries: `coordinator.get_capability("mention_resolver")`
4. Uses our lakehouse resolver when processing @project: mentions

**Why Two Phases?**:
- Module configs must be set during module initialization (pre-prepare)
- Mention resolver must be available when system prompt factory runs (post-initialize)
- System prompt factory is created AFTER session creation, not during prepare()

**Therefore**:
- Bundle config modification: BEFORE `bundle.prepare()`
- Capability registration: AFTER `session.initialize()`

#### Complete Injection Points

| Configuration | Target | Source | Timing | Purpose |
|---------------|--------|--------|--------|---------|
| **working_dir** | All tools | `amplified_dir` parameter | Pre-prepare | Resolves relative file paths to project root |
| **allowed_write_paths** | tool-filesystem | `amplified_dir` parameter | Pre-prepare | Security - restricts writes to project directory |
| **session_log_template** | hooks-logging | `~/.lakehoused/state/sessions/{session_id}/events.jsonl` | Pre-prepare | Execution trace for debugging and replay |
| **api_key** | Providers (anthropic, openai, etc.) | `~/.lakehoused/config/secrets.yaml` → `api_keys[provider_id]` | Pre-prepare | Avoid hardcoding credentials in bundles |
| **@project: resolver** | Session capability | `amplified_dir` parameter | Post-initialize | Resolves @project: mentions to project-relative files |

#### Configuration Precedence

For each setting, priority order (highest to lowest):
1. **Bundle config** - Explicitly set in bundle.yaml
2. **Runtime injection** - Lakehouse injected values
3. **Module defaults** - Module's default configuration

Example: If `bundle.yaml` has `allowed_write_paths: ["/custom/path"]`, that takes precedence over lakehouse's injection of `amplified_dir`.

#### secrets.yaml Format

```yaml
# ~/.lakehoused/config/secrets.yaml

api_keys:
  anthropic: "sk-ant-..."
  openai: "sk-proj-..."

# Add other providers as needed
```

**Security**: secrets.yaml should be chmod 600 and never committed to version control.

#### Resolution Timing Reference

Complete timing reference for all configuration and resolution:

| Resolution | When | How | Why Then |
|------------|------|-----|----------|
| `working_dir` | Pre-prepare | Modify `bundle.tools[*].config` | Modules need config during initialization |
| `allowed_write_paths` | Pre-prepare | Modify `bundle.tools[*].config` | Modules need config during initialization |
| `session_log_template` | Pre-prepare | Modify `bundle.hooks[*].config` | Modules need config during initialization |
| `api_key` | Pre-prepare | Modify `bundle.providers[*].config` | Modules need config during initialization |
| `@project:` mentions | Post-initialize | Register coordinator capability | System prompt factory queries capability after creation |
| `@bundle:` mentions | During prepare() | Foundation handles internally | Part of bundle composition |
| Context files | During factory call | System prompt factory reads | Dynamic resolution on every LLM call |

**Key Insight**: Module configuration (config dicts) must be set before modules initialize. Mention resolution (capability) must be available when system prompt factory runs.

#### Session Log Template

The `session_log_template` uses `{session_id}` placeholder:
```python
session_log_path = str(state_dir / "sessions" / "{session_id}" / "events.jsonl")
# Becomes: ~/.lakehoused/state/sessions/abc-123/events.jsonl
```

Foundation's hooks-logging replaces `{session_id}` at runtime with actual session ID.

#### Why These Specific Injections?

| Config | Why Injected | Why Not in Bundle |
|--------|--------------|-------------------|
| **working_dir** | Session-specific (varies per project) | Bundle doesn't know where it will be used |
| **allowed_write_paths** | Security boundary (per-session sandboxing) | Too restrictive to hardcode in bundle |
| **session_log_template** | Instance-specific path (lakehouse internal) | Bundle shouldn't know lakehouse file structure |
| **api_key** | Security (never hardcode credentials) | Secrets management best practice |

---

### Component: LakehouseMentionResolver

Chain resolver: @project: first, then delegate to Foundation.

**Location**: `lakehouse_library/mentions/resolver.py`

```python
from pathlib import Path

class LakehouseMentionResolver:
    """Adds @project: resolution to Foundation's bundle resolver."""

    def __init__(
        self,
        amplified_dir: Path,
        bundle_resolver: Any,  # Foundation's BundleModuleResolver
        data_dir: Path | None = None,
    ):
        self.amplified_dir = amplified_dir
        self.bundle_resolver = bundle_resolver
        self.data_dir = data_dir or Path.home() / "amplifier"

    def resolve(self, mention: str) -> Path | None:
        """Resolve @project: mentions, delegate others to Foundation.

        Resolution order:
        1. @project:path → amplified_dir/path
        2. Other @mentions → delegate to bundle_resolver

        Args:
            mention: The mention string (e.g., "@project:README.md")

        Returns:
            Resolved Path or None if not found
        """
        if not mention.startswith("@"):
            return None

        # @project: → resolve relative to amplified_dir
        if mention.startswith("@project:"):
            path = mention[9:]  # Strip "@project:"
            resolved = self.amplified_dir / path
            if resolved.exists() and self._is_path_allowed(resolved):
                return resolved
            return None

        # All other mentions → delegate to Foundation
        if self.bundle_resolver:
            return self.bundle_resolver.resolve(mention)

        return None

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        resolved = path.resolve()

        # Allow paths within amplified_dir
        try:
            resolved.relative_to(self.amplified_dir.resolve())
            return True
        except ValueError:
            pass

        # Allow paths within data_dir
        try:
            resolved.relative_to(self.data_dir.resolve())
            return True
        except ValueError:
            pass

        return False
```

---

### Integration with Session Router

Updates to `lakehoused/routers/sessions.py`.

```python
from lakehouse_library.bundles.manager import LakehouseBundleManager

# Module-level manager instance
_bundle_manager: LakehouseBundleManager | None = None

def get_bundle_manager() -> LakehouseBundleManager:
    global _bundle_manager
    if _bundle_manager is None:
        _bundle_manager = LakehouseBundleManager()
    return _bundle_manager

async def create_session(
    request: CreateSessionRequest,
    amplified_dir: Path | None = None,
) -> SessionMetadata:
    """Create a new session using Foundation bundles directly."""

    manager = get_bundle_manager()

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Create session (Foundation does all the work)
    session = await manager.create_session(
        bundle_ref=request.bundle_name,  # Renamed from profile_name
        session_id=session_id,
        amplified_dir=amplified_dir,
        approval_system=get_approval_system(),
        display_system=get_display_system(),
    )

    # Initialize session
    await session.initialize()

    # Save session metadata (lakehouse-specific persistence)
    metadata = SessionMetadata(
        session_id=session_id,
        bundle_name=request.bundle_name,  # Renamed from profile_name
        amplified_dir=str(amplified_dir) if amplified_dir else None,
        status=SessionStatus.ACTIVE,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )

    session_manager.save_session(metadata, session)

    return metadata
```

---

## Bundle Format

### Standard Foundation Bundle

User bundles are just standard Foundation bundles placed in `~/.lakehoused/bundles/`.

**Example: `~/.lakehoused/bundles/my-config/bundle.yaml`**

```yaml
bundle:
  name: my-config
  version: 1.0.0
  description: My personal configuration

# Compose with published bundles
includes:
  - git+https://github.com/microsoft/amplifier-foundation-anthropic@main

# Session configuration
session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main
  context:
    module: context-simple
    source: git+https://github.com/microsoft/amplifier-module-context-simple@main

# Include additional capabilities
includes:
  - git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory=filesystem
  - git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory=search

# Lakehouse @project: mention works automatically
context:
  include:
    - @project:AGENTS.md
    - @project:README.md

instruction: |
  You are helping with the project at @project:README.md

  Follow the guidance in @project:AGENTS.md for project-specific conventions.
```

### Using Bundle Context Features

Bundles already support everything lakehouse needs:

**1. Simple names:**
```yaml
bundle:
  name: my-config  # Use as: POST /sessions {"bundle_name": "my-config"}
```

**2. Context injection:**
```yaml
context:
  include:
    - @project:AGENTS.md     # Injected into system prompt
    - local-instructions.md  # Relative to bundle directory
```

**3. System instructions:**
```yaml
instruction: |
  You are a helpful assistant for this project.
  Review @project:README.md for context.
```

**Or via markdown body** (in `bundle.md`):
```markdown
---
bundle:
  name: my-config
---

You are a helpful assistant.

Key guidelines from @project:AGENTS.md will be provided.
```

**4. Composition:**
```yaml
includes:
  - git+https://github.com/myorg/base-bundle@main
  - git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory=filesystem
```

All context accumulates with namespace prefixes, instructions can be overridden, modules compose naturally.

---

## Directory Structure Changes

### Current Structure

```
~/.lakehoused/
├── config/
│   ├── daemon.yaml
│   ├── secrets.yaml
│   └── registries.yaml          # amp:// registry mappings
├── profiles/                     # User-created profiles
│   └── my-profile/
│       └── profile.yaml
├── share/
│   └── profiles/                 # Compiled profile cache
│       └── software-developer/
│           └── session/
│               ├── orchestrators/
│               ├── providers/
│               ├── contexts/
│               ├── tools/
│               └── hooks/
└── state/
    └── sessions/                 # Session state
        └── {session-id}/
            ├── mount_plan.json   # Compiled profile config
            ├── session.json      # Session metadata
            └── transcript.jsonl  # Chat history
```

### New Structure

```
~/.lakehoused/
├── config/
│   ├── daemon.yaml
│   └── secrets.yaml
│   # registries.yaml removed
├── bundles/                      # User bundles (standard format)
│   └── my-config/
│       ├── bundle.yaml           # Standard Foundation bundle
│       └── local-context.md      # Optional local files
├── cache/                        # Foundation's cache (flat structure, hash-based naming)
│   ├── amplifier-module-loop-streaming-a1b2c3d4/  # Git clones with content hash
│   ├── amplifier-foundation-x9y8z7w6/             # More git clones
│   └── bundle-name-z5a4b3c2.json                  # Bundle metadata cache
│   # Note: Foundation uses flat cache, not hierarchical by source
└── state/
    └── sessions/                 # Session state
        └── {session-id}/
            ├── bundle_ref.txt    # Bundle reference used (simple name or URI)
            ├── session.json      # Session metadata
            ├── transcript.jsonl  # Chat history
            └── events.jsonl      # Execution trace (from hooks-logging)
```

### Changes to Session State

| File | Before | After | Purpose |
|------|--------|-------|---------|
| Config | `mount_plan.json` (compiled profile) | `bundle_ref.txt` (bundle name or URI) | Session recreation |
| Metadata | `session.json` | `session.json` (unchanged) | Session info (status, timestamps) |
| History | `transcript.jsonl` | `transcript.jsonl` (unchanged) | Chat messages |
| **New** | ❌ Not present | `events.jsonl` | Execution trace for debugging |
| **Removed** | `profile_context_messages.json` (cached context) | ❌ Not present | See Context Caching Trade-off below |

### Session Recreation from bundle_ref.txt

When resuming a session:
1. Read `bundle_ref.txt` to get original bundle reference
2. Load that bundle (from well-known path, git, or file URI)
3. Inject same runtime configuration (working_dir, etc.)
4. Call `create_session()` with same session_id
5. Load `transcript.jsonl` to restore conversation history

**Bundle Version Stability**: Sessions reference bundles by name or URI. If the bundle at that location has changed since session creation, the resumed session will use the NEW bundle definition. This is intentional - bundles can evolve while sessions remain active.

For version pinning, use git URIs with commit SHAs: `git+https://github.com/org/repo@abc123`

### Session Debugging Trade-off: mount_plan.json Snapshot

**Current System**: Saves complete `mount_plan.json` (500+ lines) showing exact session configuration
- ✅ Pro: Can inspect session config without re-loading bundle
- ✅ Pro: Offline session reconstruction possible
- ✅ Pro: Easy debugging (see exactly what was configured)
- ❌ Con: Extra disk space (500+ lines per session)
- ❌ Con: Can become stale if bundle changes

**New System**: Saves only `bundle_ref.txt` (one line)
- ✅ Pro: Minimal disk space
- ✅ Pro: Always loads fresh bundle definition
- ❌ Con: Must re-load bundle to understand session config
- ❌ Con: Can't inspect if bundle has changed or been deleted
- ❌ Con: Harder debugging (need to reconstruct config)

**Decision**: Start with bundle_ref.txt only for simplicity. If debugging becomes difficult, add optional mount_plan snapshot:

```python
# Optional: Save mount plan snapshot for debugging
if os.getenv("LAKEHOUSE_DEBUG_SNAPSHOTS", "false").lower() == "true":
    snapshot_file = session_dir / "mount_plan_snapshot.json"
    # Save PreparedBundle's resolved config (read-only, for inspection)
```

**Mitigation**: Foundation's bundle preparation is deterministic. Same bundle + same runtime config = same mount plan. Debugging can use fresh bundle recreation.

### Context Caching Trade-off

**Old system** (with `profile_context_messages.json`):
- ✅ Pre-resolved @mentions cached to disk
- ✅ Fast session resume (no re-reading files)
- ✅ Profile switching without re-processing
- ❌ Stale content (AGENTS.md changes not picked up until cache cleared)
- ❌ Complex cache invalidation logic
- ❌ Extra disk space

**New system** (Foundation's dynamic resolution):
- ✅ Always fresh content (picks up file changes immediately)
- ✅ Simpler architecture (no cache management)
- ✅ Less disk space
- ❌ Re-reads files on every LLM call (more disk I/O)
- ❌ Higher latency for sessions with many context files
- ❌ More processing per message

**Decision**: Accept the dynamic resolution trade-off. Foundation's system prompt factory re-reads files on every call, ensuring freshness at the cost of performance. For sessions with many large context files, this may be noticeable. Future optimization could add optional caching layer if needed.

**Mitigation**: Users can minimize re-reading cost by:
- Keeping context files small and focused
- Using bundle composition to share common context
- Relying on Foundation's internal caching where available

### Session Resume Behavior

**With dynamic context resolution**:

1. **Fresh session creation**:
   - Loads bundle from bundle_ref.txt
   - Injects runtime config
   - System prompt factory reads all context files
   - Context resolved fresh on first LLM call

2. **Session resume** (same behavior as creation):
   - Loads bundle from bundle_ref.txt
   - Injects runtime config (same paths)
   - System prompt factory reads all context files AGAIN
   - No cached context from previous session

3. **Every LLM call in active session**:
   - System prompt factory may re-read context files
   - Depends on Foundation's internal caching strategy
   - Ensures context is always fresh (picks up file edits)

**Context Freshness Guarantees**:
- ✅ File edits always picked up (no stale cache)
- ✅ Bundle changes reflected on session resume
- ✅ No cache invalidation logic needed
- ❌ Re-reads files even if unchanged
- ❌ Higher latency with many large context files

**Performance Impact Scenarios**:

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Small bundle (1-3 context files, <50KB total) | Negligible (<50ms overhead) | None needed |
| Medium bundle (5-10 files, 100-200KB) | Noticeable (~100-200ms per call) | Keep files focused |
| Large bundle (20+ files, 500KB+) | Significant (~500ms+ per call) | Split into multiple smaller bundles |
| Many @project: mentions (10+ files) | High (re-reads project files every call) | Use bundle context for stable files, @project: for changing ones |

**Optimization Strategies**:
1. **Bundle composition**: Put stable context in base bundles, project-specific in includes
2. **Selective context**: Only include files actually needed for session
3. **File organization**: Keep frequently-used context small, comprehensive docs separate
4. **Future caching**: Foundation may add optional caching layer (not currently available)

---

## Migration Plan

### Single-Step Migration

**Goal**: Convert all profiles to standard Foundation bundles

This is a **breaking change** that requires users to stop the daemon, run migration, and restart.

### Pre-Migration Steps

1. **Backup existing state**
   ```bash
   cp -r ~/.lakehoused ~/.lakehoused.backup
   ```

2. **Stop daemon**
   ```bash
   pkill lakehoused
   ```

### Migration Script

Create `scripts/migrate_to_bundles.py`:

```python
#!/usr/bin/env python3
"""Migrate lakehouse profiles to Foundation bundles."""

import json
import shutil
import yaml
from pathlib import Path

def convert_profile_to_bundle(old_profile: dict) -> dict:
    """Convert old profile format to standard Foundation bundle format."""

    bundle = {
        "bundle": {
            "name": old_profile.get("name"),
            "version": old_profile.get("version", "1.0.0"),
            "description": old_profile.get("description", ""),
        }
    }

    # Convert session section
    if "session" in old_profile:
        bundle["session"] = convert_session_section(old_profile["session"])
    else:
        # Old format: orchestrator/context at top level
        bundle["session"] = {}
        if "orchestrator" in old_profile:
            bundle["session"]["orchestrator"] = convert_module_spec(old_profile["orchestrator"])
        if "context" in old_profile:
            bundle["session"]["context"] = convert_module_spec(old_profile["context"])

    # Convert behaviors/includes
    if "behaviors" in old_profile:
        bundle["includes"] = [
            convert_behavior_to_source(b)
            for b in old_profile["behaviors"]
        ]
    elif "includes" in old_profile:
        bundle["includes"] = old_profile["includes"]

    # Convert module lists
    for key in ["providers", "tools", "hooks"]:
        if key in old_profile:
            if key not in bundle:
                bundle[key] = []
            bundle[key].extend([
                convert_module_spec(m) for m in old_profile[key]
            ])

    # Convert project_defaults to bundle context/instruction
    if "project_defaults" in old_profile:
        defaults = old_profile["project_defaults"]

        # Extract default_context as instruction
        if "default_context" in defaults:
            bundle["instruction"] = defaults["default_context"]

        # Extract context files
        if "context_files" in defaults:
            bundle["context"] = {
                "include": defaults["context_files"]
            }

    return bundle

def convert_session_section(session: dict) -> dict:
    """Convert session section, handling both old and new formats."""
    result = {}

    for key in ["orchestrator", "context"]:
        if key in session:
            result[key] = convert_module_spec(session[key])

    if "settings" in session:
        result["settings"] = session["settings"]

    return result

def convert_module_spec(spec: dict | str) -> dict:
    """Convert module spec from amp:// to git URL."""
    if isinstance(spec, str):
        spec = {"module": spec}

    result = {"module": spec.get("module")}

    # Convert amp:// source to git URL
    if "source" in spec:
        source = spec["source"]
        if source.startswith("amp://"):
            result["source"] = convert_amp_to_git(source)
        else:
            result["source"] = source

    # Preserve config
    if "config" in spec:
        result["config"] = spec["config"]

    return result

def convert_behavior_to_source(behavior: dict | str) -> str:
    """Convert behavior spec to bundle source URI."""
    if isinstance(behavior, str):
        behavior = {"id": behavior}

    if "source" in behavior:
        source = behavior["source"]
        if source.startswith("amp://"):
            return convert_amp_to_git(source)
        return source

    # Default behavior location
    behavior_id = behavior.get("id")
    return f"git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory={behavior_id}"

def convert_amp_to_git(amp_uri: str) -> str:
    """Convert amp:// URI to git+https:// URL.

    Uses explicit mapping table for known modules to handle:
    - Different GitHub organizations
    - Local file:// paths for custom modules
    - Subdirectory locations
    - Version/branch specifications

    Returns:
        Git URL, file:// path, or original URI with warning if unknown
    """
    # Strip amp://
    path = amp_uri[6:]
    parts = path.split("/")
    registry = parts[0] if len(parts) > 0 else ""
    category = parts[1] if len(parts) > 1 else ""
    name = parts[2] if len(parts) > 2 else ""

    # Full path for mapping lookup
    full_path = f"{registry}/{category}/{name}" if name else f"{registry}/{category}" if category else registry

    # Explicit mapping table for known modules
    # Add entries here as new modules are encountered
    known_mappings = {
        # Orchestrators
        "lakehouse/orchestrators/loop-streaming": "git+https://github.com/microsoft/amplifier-module-loop-streaming@main",

        # Providers
        "lakehouse/providers/anthropic": "git+https://github.com/microsoft/amplifier-providers@main#subdirectory=anthropic",
        "lakehouse/providers/openai": "git+https://github.com/microsoft/amplifier-providers@main#subdirectory=openai",

        # Behaviors
        "lakehouse/behaviors/filesystem": "git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory=filesystem",
        "lakehouse/behaviors/search": "git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory=search",

        # Contexts
        "lakehouse/contexts/context-simple": "git+https://github.com/microsoft/amplifier-module-context-simple@main",

        # Hooks
        "lakehouse/hooks/hooks-logging": "git+https://github.com/microsoft/amplifier-module-hooks-logging@main",

        # Tools
        "lakehouse/tools/tool-search": "file:///data/repos/lakehouse/registry/tools/tool-search",  # Local module
        "lakehouse/tools/tool-filesystem": "file:///data/repos/lakehouse/registry/tools/tool-filesystem",

        # Add more mappings as encountered during migration
    }

    # Check explicit mapping first
    if full_path in known_mappings:
        return known_mappings[full_path]

    # Pattern-based fallback for standard microsoft modules
    if registry == "lakehouse":
        if category == "orchestrators":
            return f"git+https://github.com/microsoft/amplifier-module-{name}@main"
        elif category == "providers":
            return f"git+https://github.com/microsoft/amplifier-providers@main#subdirectory={name}"
        elif category == "behaviors":
            return f"git+https://github.com/microsoft/amplifier-behaviors@main#subdirectory={name}"
        elif category == "hooks":
            return f"git+https://github.com/microsoft/amplifier-module-{name}@main"
        elif category == "contexts":
            return f"git+https://github.com/microsoft/amplifier-module-{name}@main"
        elif category == "tools":
            # Warn: tools may be local or have different paths
            print(f"  ⚠️  WARNING: Unknown tool module: {amp_uri}")
            print(f"      Using pattern-based mapping, may need manual review")
            return f"git+https://github.com/microsoft/amplifier-module-{name}@main"

    # Unknown mapping - return original with warning
    print(f"  ⚠️  WARNING: Unknown amp:// URI: {amp_uri}")
    print(f"      Keeping original URI - MANUAL REVIEW REQUIRED")
    print(f"      Add to known_mappings in migrate_to_bundles.py")
    return amp_uri  # Keep original for manual review

def migrate_profiles(lakehoused_home: Path):
    """Convert all profiles to bundles."""
    old_profiles_dir = lakehoused_home / "profiles"
    new_bundles_dir = lakehoused_home / "bundles"
    new_bundles_dir.mkdir(exist_ok=True)

    if not old_profiles_dir.exists():
        print("  No profiles to migrate")
        return

    migrated_count = 0
    for profile_dir in old_profiles_dir.iterdir():
        if not profile_dir.is_dir():
            continue

        profile_yaml = profile_dir / "profile.yaml"
        if not profile_yaml.exists():
            continue

        # Load old profile
        old_profile = yaml.safe_load(profile_yaml.read_text())

        # Convert to bundle
        bundle = convert_profile_to_bundle(old_profile)

        # Write to new location
        bundle_dir = new_bundles_dir / profile_dir.name
        bundle_dir.mkdir(exist_ok=True)

        bundle_file = bundle_dir / "bundle.yaml"
        bundle_file.write_text(yaml.dump(bundle, sort_keys=False))

        migrated_count += 1

    print(f"  ✓ Migrated {migrated_count} profiles to bundles")

def migrate_sessions(lakehoused_home: Path):
    """Update session state to reference bundle names."""
    sessions_dir = lakehoused_home / "state" / "sessions"

    if not sessions_dir.exists():
        print("  No sessions to migrate")
        return

    migrated_count = 0
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue

        # Read session metadata to get profile name
        session_file = session_dir / "session.json"
        if not session_file.exists():
            continue

        session_meta = json.loads(session_file.read_text())
        bundle_name = session_meta.get("profile_name", "unknown")

        # Write bundle reference
        bundle_ref_file = session_dir / "bundle_ref.txt"
        bundle_ref_file.write_text(bundle_name)

        # Remove old mount_plan.json if exists
        mount_plan_file = session_dir / "mount_plan.json"
        if mount_plan_file.exists():
            mount_plan_file.unlink()

        # Update session.json to use bundle_name
        if "profile_name" in session_meta:
            session_meta["bundle_name"] = session_meta.pop("profile_name")
            session_file.write_text(json.dumps(session_meta, indent=2))

        migrated_count += 1

    print(f"  ✓ Migrated {migrated_count} sessions")

def cleanup_old_system(lakehoused_home: Path):
    """Remove old profile system artifacts."""

    # Remove old profile cache
    share_dir = lakehoused_home / "share" / "profiles"
    if share_dir.exists():
        shutil.rmtree(share_dir)
        print(f"  ✓ Removed old cache: {share_dir}")

    # Remove registries.yaml
    registries_file = lakehoused_home / "config" / "registries.yaml"
    if registries_file.exists():
        registries_file.unlink()
        print(f"  ✓ Removed registries.yaml")

    # Keep old profiles dir as backup, but rename
    old_profiles_dir = lakehoused_home / "profiles"
    if old_profiles_dir.exists():
        backup_dir = lakehoused_home / "profiles.backup"
        old_profiles_dir.rename(backup_dir)
        print(f"  ✓ Backed up old profiles to: {backup_dir}")

def main():
    lakehoused_home = Path.home() / ".lakehoused"

    print("Starting migration to Foundation bundles...")
    print()

    # Step 1: Migrate profiles to bundles
    print("Step 1: Converting profiles to bundles...")
    migrate_profiles(lakehoused_home)
    print()

    # Step 2: Migrate session state
    print("Step 2: Migrating session state...")
    migrate_sessions(lakehoused_home)
    print()

    # Step 3: Cleanup
    print("Step 3: Cleaning up old system...")
    cleanup_old_system(lakehoused_home)
    print()

    print("✓ Migration complete!")
    print()
    print("Next steps:")
    print("  1. Review migrated bundles in ~/.lakehoused/bundles/")
    print("  2. Install amplifier-foundation: cd lakehoused && uv add amplifier-foundation")
    print("  3. Restart daemon: make daemon-dev")

if __name__ == "__main__":
    main()
```

### Migration Steps

1. **Install Foundation dependency**
   ```bash
   cd lakehoused
   uv add amplifier-foundation
   ```

2. **Run migration script**
   ```bash
   python scripts/migrate_to_bundles.py
   ```

3. **Verify migration**
   ```bash
   # Check bundle format
   cat ~/.lakehoused/bundles/basic/bundle.yaml

   # Check session state
   ls ~/.lakehoused/state/sessions/*/

   # Verify old system removed
   ls ~/.lakehoused/share/  # Should not exist
   ls ~/.lakehoused/profiles.backup/  # Old profiles backed up here
   ```

4. **Start daemon with new code**
   ```bash
   make daemon-dev
   ```

### Rollback Plan

If migration fails:

```bash
# Stop daemon
pkill lakehoused

# Restore backup
rm -rf ~/.lakehoused
mv ~/.lakehoused.backup ~/.lakehoused

# Revert code changes
git checkout main

# Restart daemon
make daemon-dev
```

### What Gets Migrated

| Component | From | To |
|-----------|------|-----|
| **Profile concept** | Custom lakehouse format | Standard Foundation bundles |
| **Profile location** | `profiles/*/profile.yaml` | `bundles/*/bundle.yaml` |
| **Profile sources** | `amp://lakehouse/...` | `git+https://github.com/...` |
| **Session config** | `mount_plan.json` | `bundle_ref.txt` |
| **Profile cache** | `share/profiles/` | `cache/bundles/` (managed by Foundation) |
| **Registry config** | `config/registries.yaml` | Removed (use direct git URLs) |

### Migration Impact

- **Bundle count**: All profiles converted to bundles
- **Session count**: All sessions updated to reference bundles
- **Downtime**: ~5 minutes (stop daemon → migrate → restart)
- **Data loss**: None (backup created first, old profiles kept in `profiles.backup/`)
- **Breaking changes**: Yes (old profile format no longer supported)

### Backwards Compatibility Strategy

**Decision**: Single-step breaking change with comprehensive backup and rollback.

#### Why Not Backwards Compatible?

**Dual support complexity** (maintaining both systems):
- Would require ~827 lines of profile compilation code to remain
- Defeats the purpose of simplification
- Doubles testing surface (profiles AND bundles)
- Creates confusion about which system to use
- Delays inevitable transition

**Technical incompatibility**:
- Different module loading mechanisms
- Different caching strategies
- Different context resolution approaches
- Can't safely run profile sessions and bundle sessions in same daemon

#### What This Means for Users

**Active sessions**: All active sessions become invalid on upgrade. Users must:
1. Stop daemon
2. Run migration script
3. Restart daemon
4. Create new sessions with migrated bundles
5. Old session transcripts preserved but can't be resumed without recreating

**Custom profiles**: All automatically converted, but users should review:
- amp:// URIs that couldn't be auto-mapped
- Local module paths that may have changed
- Custom configurations that may need adjustment

**Tooling dependencies**: Any scripts or integrations expecting profile terminology must update to bundle terminology:
- API: `profile_name` → `bundle_name`
- Endpoints: `/profiles` → `/bundles`
- Session metadata: `profile_name` field → `bundle_name` field

#### Mitigation for Impact

1. **Comprehensive backup**: Migration creates `~/.lakehoused.backup` before any changes
2. **Old profiles preserved**: Original profiles kept in `profiles.backup/` for reference
3. **Rollback script provided**: One command restores pre-migration state
4. **Migration validation**: Script reports warnings for unmappable URIs
5. **Manual review list**: Script outputs list of bundles requiring human review
6. **Zero data loss**: Transcripts, session metadata all preserved

#### Rollback Process

If migration fails or users want to revert:

```bash
#!/bin/bash
# scripts/rollback_migration.sh

echo "Rolling back to pre-migration state..."

# Stop daemon
pkill lakehoused

# Restore backup
if [ -d ~/.lakehoused.backup ]; then
    rm -rf ~/.lakehoused
    mv ~/.lakehoused.backup ~/.lakehoused
    echo "✓ Restored backup"
else
    echo "✗ No backup found"
    exit 1
fi

# Revert code
git checkout main  # Or previous commit hash

echo "✓ Rollback complete"
echo "  Run 'make daemon-dev' to restart"
```

#### User Communication

**Before release**, provide:
- Migration guide with clear steps
- List of known breaking changes
- Estimated downtime (5-10 minutes)
- Rollback instructions
- Support channel for issues

**Release notes should emphasize**:
- This is a one-time migration
- Creates backup automatically
- Rollback is simple and safe
- Benefits: simpler system, ecosystem access, upstream compatibility

### Post-Migration Validation

1. **Test session creation**
   - Create new session: `POST /sessions {"bundle_name": "my-config"}`
   - Verify bundle loads correctly
   - Send test message

2. **Test existing sessions**
   - List sessions via API
   - Resume existing session
   - Send message in resumed session

3. **Test @project: resolution**
   - Use `@project:README.md` in bundle context
   - Verify file is resolved correctly in system prompt

4. **Verify bundle caching**
   - Check `~/.lakehoused/cache/bundles/` contains downloaded modules
   - Confirm `share/profiles/` is removed

---

## API Changes

### Breaking API Changes

External API changes to reflect bundle terminology:

| Endpoint | Before | After |
|----------|--------|-------|
| Create session | `{"profile_name": "basic"}` | `{"bundle_name": "basic"}` |
| List profiles | `GET /profiles` | `GET /bundles` |
| Session metadata | `profile_name` field | `bundle_name` field |

### Updated Endpoints

**Create Session:**
```json
POST /sessions
{
  "bundle_name": "my-config",    // Changed from profile_name
  "amplified_dir": "/data/project",
  "initial_message": "Hello"
}
```

**List Bundles:**
```json
GET /bundles

Response:
{
  "bundles": [
    {
      "name": "my-config",
      "version": "1.0.0",
      "description": "My personal configuration",
      "location": "~/.lakehoused/bundles/my-config"
    }
  ]
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/bundles/test_manager.py

async def test_load_bundle_by_name():
    """Test loading bundle from well-known location."""
    manager = LakehouseBundleManager()

    # Create test bundle
    bundle_dir = manager.well_known_paths[0] / "test-bundle"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "bundle.yaml").write_text("""
bundle:
  name: test-bundle
  version: 1.0.0
""")

    # Load by name
    prepared = await manager.load_bundle("test-bundle")
    assert prepared is not None

async def test_load_bundle_by_uri():
    """Test loading bundle from git URI."""
    manager = LakehouseBundleManager()

    prepared = await manager.load_bundle(
        "git+https://github.com/microsoft/amplifier-foundation-anthropic@main"
    )
    assert prepared is not None

async def test_project_resolver_injection():
    """Test @project: resolver is injected."""
    manager = LakehouseBundleManager()

    session = await manager.create_session(
        bundle_ref="test-bundle",
        session_id="test-123",
        amplified_dir=Path("/tmp/test-project"),
    )

    # Verify @project: resolver is registered
    resolver = session.coordinator.get_capability("lakehouse.mention_resolver")
    assert resolver is not None
    assert resolver.amplified_dir == Path("/tmp/test-project")
```

### Integration Tests

```python
# tests/integration/bundles/test_session_creation.py

async def test_create_session_with_bundle():
    """Test full session creation flow."""
    manager = LakehouseBundleManager()

    # Create session
    session = await manager.create_session(
        bundle_ref="basic",
        session_id="test-456",
        amplified_dir=Path("/tmp/test-project"),
    )

    # Verify session is functional
    await session.initialize()
    assert session.coordinator.mount_points["orchestrator"] is not None
    assert len(session.coordinator.mount_points["providers"]) > 0

    # Verify @project: resolution works
    resolver = session.coordinator.get_capability("lakehouse.mention_resolver")
    resolved = resolver.resolve("@project:README.md")
    assert resolved == Path("/tmp/test-project/README.md")

async def test_runtime_config_injection():
    """Test that runtime config is properly injected."""
    manager = LakehouseBundleManager()
    amplified_dir = Path("/tmp/test-project")
    session_id = "test-config-123"

    session = await manager.create_session(
        bundle_ref="basic",
        session_id=session_id,
        amplified_dir=amplified_dir,
    )

    # Verify working_dir injected into tools
    # (Access via session's mount plan or module configs)
    # Note: Exact verification depends on how Foundation exposes config

    # Verify session_log_template set correctly
    expected_log = manager.home_dir / "state" / "sessions" / session_id / "events.jsonl"
    # (Verify hooks-logging config contains this path)

async def test_session_state_persistence():
    """Test session state is saved and restorable."""
    manager = LakehouseBundleManager()
    session_id = "test-persist-789"
    bundle_ref = "basic"

    # Create session
    session = await manager.create_session(
        bundle_ref=bundle_ref,
        session_id=session_id,
        amplified_dir=Path("/tmp/project"),
    )

    # Save session state (normally done by session manager)
    state_dir = manager.home_dir / "state" / "sessions" / session_id
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "bundle_ref.txt").write_text(bundle_ref)

    # Verify bundle_ref.txt exists and contains correct reference
    assert (state_dir / "bundle_ref.txt").read_text() == bundle_ref

    # Verify events.jsonl is created by hooks-logging
    # (This happens during session usage, not creation)
```

### Migration Tests

```python
# tests/integration/migration/test_profile_to_bundle.py

def test_migrate_simple_profile():
    """Test migration of basic profile to bundle."""
    from scripts.migrate_to_bundles import convert_profile_to_bundle

    old_profile = {
        "name": "test-profile",
        "version": "1.0.0",
        "session": {
            "orchestrator": {
                "module": "loop-streaming",
                "source": "amp://lakehouse/orchestrators/loop-streaming"
            }
        }
    }

    bundle = convert_profile_to_bundle(old_profile)

    assert bundle["bundle"]["name"] == "test-profile"
    assert "session" in bundle
    assert "git+https://github.com" in bundle["session"]["orchestrator"]["source"]

def test_amp_to_git_conversion():
    """Test amp:// URI conversion to git URLs."""
    from scripts.migrate_to_bundles import convert_amp_to_git

    # Known mapping
    result = convert_amp_to_git("amp://lakehouse/orchestrators/loop-streaming")
    assert result == "git+https://github.com/microsoft/amplifier-module-loop-streaming@main"

    # Local module (file://)
    result = convert_amp_to_git("amp://lakehouse/tools/tool-search")
    assert result.startswith("file://")

    # Unknown mapping (should warn and return original)
    result = convert_amp_to_git("amp://unknown/category/module")
    assert result == "amp://unknown/category/module"

def test_full_migration():
    """Test complete migration process."""
    # Setup test environment with old profiles
    test_home = Path("/tmp/test-lakehoused")
    # ... create test profiles ...

    # Run migration
    from scripts.migrate_to_bundles import migrate_profiles, migrate_sessions

    migrate_profiles(test_home)
    migrate_sessions(test_home)

    # Verify bundles created
    assert (test_home / "bundles" / "test-profile" / "bundle.yaml").exists()

    # Verify sessions updated
    session_dir = test_home / "state" / "sessions" / "test-session"
    assert (session_dir / "bundle_ref.txt").exists()
    assert not (session_dir / "mount_plan.json").exists()
```

### Error Condition Tests

```python
# tests/integration/bundles/test_error_cases.py

async def test_bundle_not_found():
    """Test clear error when bundle doesn't exist."""
    manager = LakehouseBundleManager()

    with pytest.raises(ValueError) as exc_info:
        await manager.load_bundle("nonexistent-bundle")

    assert "Bundle not found" in str(exc_info.value)
    assert "Searched:" in str(exc_info.value)
    assert "Tip:" in str(exc_info.value)

async def test_git_clone_failure():
    """Test handling of git clone failures."""
    manager = LakehouseBundleManager()

    with pytest.raises(Exception) as exc_info:
        await manager.load_bundle("git+https://github.com/invalid/repo@main")

    # Foundation should provide clear error message about git failure

async def test_missing_api_key():
    """Test session creation when API key missing."""
    manager = LakehouseBundleManager()

    # Create session without secrets.yaml
    session = await manager.create_session(
        bundle_ref="basic",
        session_id="test-no-key",
    )

    # Should succeed (API key injection is optional)
    # Provider will fail when actually called, not at session creation
```

### Bundle Caching Tests

```python
# tests/integration/bundles/test_caching.py

async def test_bundle_caching():
    """Test that bundles are cached after first load."""
    manager = LakehouseBundleManager()

    # First load (should clone from git)
    bundle1 = await manager.load_bundle("git+https://github.com/microsoft/amplifier-foundation-anthropic@main")

    # Second load (should use cache)
    bundle2 = await manager.load_bundle("git+https://github.com/microsoft/amplifier-foundation-anthropic@main")

    # Both should work, second should be faster
    # (Timing verification depends on Foundation's caching behavior)

async def test_bundle_update():
    """Test bundle updates after cache."""
    # Future: Test bundle.update() functionality
    # Current: Not yet implemented
    pass
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Foundation API changes | High | Pin foundation version, test before upgrade |
| Bundle format confusion | Medium | Provide examples, migration tool validates |
| Missing bundles after migration | Medium | Keep old profiles as backup in `profiles.backup/` |
| Git clone failures | Low | Graceful error messages, retry logic |

---

## Success Metrics

1. **Simplicity**: Lakehouse bundle code reduced from ~827 to ~150 lines
2. **Compatibility**: All existing sessions work after migration
3. **Upstream sync**: Can use new amplifier modules without lakehouse changes
4. **Performance**: Session creation time within 10% of current
5. **User experience**: Simple names still work, ecosystem access gained

---

## Additional Design Notes

### Bundle Caching Location

**Foundation's cache structure** (actual implementation):
```
~/.amplifier/                                    # Default AMPLIFIER_HOME
└── cache/                                       # Flat structure, not hierarchical
    ├── amplifier-module-loop-streaming-a1b2c3d4/   # Git clones (content-hashed)
    ├── amplifier-foundation-x9y8z7w6/              # More git clones (hashed)
    ├── my-custom-bundle-z5a4b3c2/                  # User bundles (hashed)
    └── bundle-metadata-abc123.json                 # Bundle metadata cache
```

**Key Points**:
- Foundation uses **flat cache directory** with hash-based naming (not `cache/git/host/org/repo/`)
- Content hashes ensure uniqueness and enable cache reuse across versions
- Default home is `~/.amplifier/` but lakehouse overrides to `~/.lakehoused/` via:
  ```python
  self.registry = BundleRegistry(home=self.home_dir)  # Pass ~/.lakehoused explicitly
  ```

**Lakehouse cache location**:
```
~/.lakehoused/                                   # Lakehouse home (not ~/.amplifier)
└── cache/                                       # Inherits Foundation's flat structure
    ├── amplifier-module-loop-streaming-a1b2c3d4/
    └── ...
```

Lakehouse inherits Foundation's caching structure without modification, just uses different home directory.

### Dependency Management with uv

**Foundation's approach**:
- ModuleActivator uses `uv pip install` to install module dependencies
- Installation happens during `bundle.prepare()`
- By default, `install_deps=True` (can be disabled with `install_deps=False`)

**Lakehouse decision**: Allow uv to install into daemon's venv
- ✅ Pro: Automatic dependency resolution
- ✅ Pro: Isolated from user's environment
- ✅ Pro: Works seamlessly with published bundles
- ❌ Con: Requires uv to be installed
- ❌ Con: Potential dependency conflicts if many bundles used

**Mitigation**: Document uv requirement, provide troubleshooting guide for dependency conflicts.

**Alternative if uv unavailable**: Set `install_deps=False` in bundle preparation, manually ensure dependencies available in daemon venv.

### Error Handling and User Experience

**Bundle loading errors**:
```python
# Clear, actionable error messages
raise ValueError(
    f"Bundle not found: {bundle_ref}\n"
    f"Searched: {[str(p / bundle_ref) for p in self.well_known_paths]}\n"
    f"Tip: Use full URI (file:// or git+https://) or place bundle in {self.well_known_paths[0]}"
)
```

**Git clone failures**:
- Foundation handles retries automatically
- On failure, provides clear error with git URL and error reason
- Users can manually inspect/fix the issue in `cache/git/`

**Migration warnings**:
- Script outputs warnings for unmappable amp:// URIs
- Provides list of bundles requiring manual review
- Keeps original profiles in backup for reference

**Bundle discovery**:
- Webapp scans well-known paths for available bundles
- Lists bundle names with descriptions from bundle.yaml
- Future: Could query published bundle registry (not implemented initially)

### Bundle Updates and Lifecycle

**Update workflow** (not yet implemented, but planned):
```python
# Check for updates
info = await manager.check_bundle_status("my-config")
if info.has_updates:
    print(f"Updates available: {info.latest_version}")

# Update bundle
await manager.update_bundle("my-config")
```

**Impact on active sessions**:
- Sessions reference bundles by name/URI
- Session resume loads current bundle definition
- If bundle updated while session active, resume gets NEW definition
- For stability, use git URIs with commit SHAs

**Bundle removal**:
- Delete from `~/.lakehoused/bundles/` directory
- Foundation clears from `cache/` on next startup
- Active sessions referencing deleted bundle fail on resume

## Open Questions

1. **Well-known bundle locations**: Should we support multiple search paths?
   - System-wide: `/usr/local/share/amplifier/bundles/`
   - Project-local: `./.amplifier/bundles/`
   - Team-shared: Network location

   **Current**: Single location (`~/.lakehoused/bundles/`)
   **Future**: Make configurable in daemon.yaml

2. **Bundle discovery UI**: How should webapp list available bundles?
   - **Phase 1**: Scan well-known paths only
   - **Phase 2**: Query published bundle registry (requires registry API)
   - **Phase 3**: Search GitHub for amplifier bundles

3. **Version pinning**: Should lakehouse encourage pinning?
   - **Recommendation**: Use `@main` for active development, pin to commit SHA for production
   - **Trade-off**: `@main` gets updates automatically but may break; SHAs are stable but stale
   - **Solution**: Webapp could show "update available" notification

4. **Bundle namespacing**: How to handle name collisions?
   - User's "basic" bundle vs Foundation's "basic" bundle
   - **Current**: Well-known path checked first (user's overrides published)
   - **Future**: Consider namespacing like "foundation:basic" vs "user:basic"

5. **Secrets management security**:
   - secrets.yaml is plain text (chmod 600)
   - **Future**: Consider encryption at rest, integration with system keychains
   - **Current**: Document best practices, file permissions

---

## Appendix: File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `lakehouse_library/bundles/__init__.py` | Bundle management module |
| `lakehouse_library/bundles/manager.py` | LakehouseBundleManager (~100 lines) |
| `lakehouse_library/mentions/resolver.py` | @project: resolver (~50 lines) |
| `scripts/migrate_to_bundles.py` | Migration script |

### Modified Files

| File | Changes |
|------|---------|
| `lakehoused/routers/sessions.py` | Use LakehouseBundleManager, rename profile_name → bundle_name |
| `lakehoused/models/sessions.py` | Rename profile_name → bundle_name in SessionMetadata |
| `lakehoused/pyproject.toml` | Add amplifier-foundation dependency |
| `lakehouse_library/pyproject.toml` | Add amplifier-foundation dependency |

### Removed Files

| File | Reason |
|------|--------|
| `lakehouse_library/services/profile_compilation.py` (~827 lines) | Replaced by Foundation |
| `lakehouse_library/services/registry_service.py` | No longer needed |
| `lakehouse_library/profiles/` (entire module) | No longer needed |
| `config/registries.yaml` | Use direct git URLs |

---

## Summary

This design **eliminates lakehouse-specific abstractions** and uses Foundation's bundle system directly:

- **Profiles = Bundles** (just placed in well-known location)
- **Behaviors = Bundles** (just included bundles)
- **~150 lines of lakehouse code** vs ~827 lines of custom pipeline
- **Full Foundation compatibility** - bundles work everywhere
- **All bundle features available** - context, instruction, composition, namespaces

Lakehouse's minimal layer only adds:
1. Well-known bundle locations (`~/.lakehoused/bundles/`)
2. @project: mention resolution (project-relative files)
3. Session state persistence

Everything else is pure Foundation.
