# Session Implementation Plan: Mount Plans in amplifierd

**Status**: Design Complete, Ready for Implementation
**Created**: 2025-01-25
**Author**: Coordinated by AI Agents (zen-architect, Explore)

---

## Executive Summary

This plan outlines how to add mount plan generation capabilities to amplifierd, enabling it to convert cached profile resources into mount plans that amplifier-core can use to create sessions.

**Core Insight**: We already have the hard parts (profile caching, resource resolution). Mount plans are just **structured views** of cached resources with session context. This is primarily about **serialization and presentation**, not complex transformation.

**Key Deliverable**: RESTful APIs that transform `ProfileDetails` + cached resources → `MountPlan` compatible with amplifier-core.

**Architecture Context**: amplifierd is the backend service for a web application. Settings management, user preferences, and configuration are handled by the web app layer and passed to amplifierd via API requests. We are NOT implementing CLI-style settings resolution (config files, environment variables, CLI flags) - that's the domain of terminal-based tools like amplifier-app-cli.

---

## 1. Background & Context

### 1.1 Current State: amplifierd Profile Caching

amplifierd implements a comprehensive caching system:

**What's Cached**:
- Profile manifests (`.md` files with YAML frontmatter, schema v2)
- All referenced resources: agents, context, orchestrators, context-managers, providers, tools, hooks
- Git repository checkouts (commit-based deduplication)

**Where It's Cached**:
```
.amplifierd/
  share/
    profiles/
      {collection-id}/
        {profile-name}/
          {profile-name}.md      # Manifest copy
          agents/*.md            # Agent files
          context/*/             # Context directories
          orchestrator/{hash}/   # Module checkouts
          providers/{hash}/      # Module checkouts
          tools/{hash}/          # Module checkouts
          hooks/{hash}/          # Module checkouts
```

**Services Involved**:
- `ProfileService` - Profile lifecycle management
- `ProfileDiscoveryService` - Find and parse profiles in collections
- `ProfileCompilationService` - Resolve refs and create cache structure
- `RefResolutionService` - Resolve git+URLs, local paths, fsspec URIs
- `CollectionService` - Sync collections and trigger discovery

**Key Models**:
- `ProfileDetails` - Pydantic model for schema v2 profiles
- `ModuleConfig` - Module reference with source and config
- `SessionConfig` - Orchestrator + context-manager configuration

### 1.2 Reference: amplifier-app-cli Mount Plans

**Note**: amplifier-app-cli is a separate terminal-based tool that we are NOT modifying. It serves as a reference implementation showing how mount plans work with amplifier-core. We're implementing similar functionality in amplifierd, but adapted for a web app use case (no terminal-based settings resolution).

The amplifier CLI demonstrates how mount plans work:

**Mount Plan Structure**:
```python
{
    "session": {
        "session_id": "session_abc123",
        "orchestrator": "loop-streaming",
        "context": "multi-turn",
        "max_turns": 10,
        # ... other session settings
    },
    "orchestrator": {
        "module_id": "loop-streaming",
        "config": {...}
    },
    "context": {
        "multi-turn": {
            "module_id": "multi-turn",
            "config": {...}
        }
    },
    "agents": {
        "zen-architect": {
            "content": "...",  # Agent markdown content
            "metadata": {...}
        }
    },
    "providers": [...],
    "tools": [...],
    "hooks": [...]
}
```

**Key Patterns** (relevant to amplifierd):
1. **Deep merging by module ID**: Child profiles only specify differences from parents
2. **Agent overlays**: Enable sub-session customization (session delegation)
3. **Module resolution**: Git refs, file paths, or installed packages
4. **Session lifecycle**: Mount plan → AmplifierSession(config) → initialize() → execute()

**Note**: amplifier-app-cli implements a settings hierarchy (CLI flags > local > project > user > profile > defaults) for terminal use. amplifierd does NOT implement this - the web app handles settings in its own way and passes final values via `settings_overrides` in API requests.

### 1.3 The Gap: What We Need to Build

**What's Missing**:
1. ❌ No `MountPlan` data model
2. ❌ No API to generate mount plans from cached profiles
3. ❌ No mount plan persistence or querying
4. ❌ No support for session delegation (sub-sessions)
5. ❌ No validation of mount plans

**What We Have** (Building Blocks):
1. ✅ Profile manifests cached in share dir
2. ✅ All resources resolved and available locally
3. ✅ `ProfileDetails` model with all manifest data
4. ✅ RESTful API infrastructure (FastAPI)
5. ✅ Pydantic validation patterns
6. ✅ Storage utilities

**What We're Building**: A bridge from cached profiles → structured mount plans.

---

## 2. Architecture Overview

### 2.1 Complete Data Flow

```
┌────────────────────────────────────────────────────────┐
│ EXISTING: Profile Caching                              │
└────────────────────────────────────────────────────────┘
  Collection Sync → Profile Discovery → Profile Compilation
                                              ↓
                        share/profiles/{collection}/{profile}/
                        ├── agents/*.md (embed content)
                        ├── context/*.md (embed content)
                        └── providers/*.py (reference with file://)
                                              ↓
┌────────────────────────────────────────────────────────┐
│ NEW: Session Creation & State Management               │
└────────────────────────────────────────────────────────┘
  1. Generate Mount Plan (embedded + referenced mounts)
     ↓
  2. Create Session State (CREATED)
     ↓
  3. Persist to state/sessions/{session_id}/
     ├── mount_plan.json
     ├── session.json
     └── transcript.jsonl (empty)
                                              ↓
┌────────────────────────────────────────────────────────┐
│ Session Lifecycle                                      │
└────────────────────────────────────────────────────────┘
  Start (CREATED → ACTIVE)
     ↓
  Messages Appended to transcript.jsonl
     ↓
  End (ACTIVE → COMPLETED/FAILED/TERMINATED)
                                              ↓
┌────────────────────────────────────────────────────────┐
│ FUTURE: amplifier-core Integration                    │
└────────────────────────────────────────────────────────┘
  Load Mount Plan → Initialize Modules → Execute Session
```

### 2.2 New Components

**Mount Plan Models** (`amplifierd/models/mount_plans.py`):
- `EmbeddedMount` - For agents/context with content embedded
- `ReferencedMount` - For modules with file:// paths
- `MountPoint` - Union of EmbeddedMount | ReferencedMount
- `MountPlan` - Complete mount plan with organized resources
- `MountPlanRequest` - API request to generate plan

**Session State Models** (`amplifierd/models/sessions.py`):
- `SessionStatus` - Enum: CREATED, ACTIVE, COMPLETED, FAILED, TERMINATED
- `SessionMetadata` - Session state (status, timestamps, metrics)
- `SessionMessage` - Single message in transcript
- `SessionIndex` - Fast lookup index for queries

**Services**:
- `MountPlanService` (`amplifierd/services/mount_plan_service.py`) - Generate mount plans from profiles
- `SessionStateService` (`amplifierd/services/session_state_service.py`) - Manage session lifecycle and persistence

**API Routers**:
- `mount_plans.py` - Mount plan generation and querying
- `sessions.py` - Session lifecycle, transcripts, queries

### 2.3 Session State Management

**Session Lifecycle**:
```
CREATE → ACTIVE → (COMPLETED | FAILED | TERMINATED)
   ↓       ↓                    ↓
 Mount   Messages            Cleanup
  Plan   Appended            Eligible
```

**Storage Per Session**:
```
.amplifierd/state/sessions/
  session_abc123/
    mount_plan.json       # Generated once (EmbeddedMount + ReferencedMount)
    session.json          # Updated on state changes (status, timestamps, metrics)
    transcript.jsonl      # Appended as messages exchanged
```

**Key Design Decisions**:
1. **Separate files**: Small metadata (session.json) + large transcript (transcript.jsonl)
2. **Append-only transcript**: Efficient message logging, no file rewrites
3. **Atomic updates**: State changes use tmp + rename pattern
4. **Fast index**: Single index.json enables queries without scanning all sessions

**Status Enum**:
- `CREATED`: Session exists, mount plan generated, not yet started
- `ACTIVE`: Session running, messages being exchanged
- `COMPLETED`: Session finished successfully
- `FAILED`: Session ended with error
- `TERMINATED`: Session killed by user

**Metrics Tracked**:
- Message count
- Agent invocations
- Token usage
- Duration (created → ended)

### 2.4 Integration Points

**With Existing Services**:
- `ProfileService.get_profile()` - Source of cached profile data
- `get_share_dir()` - Path to cached resources
- FastAPI dependency injection - Wire up new service

**With Future Components**:
- `amplifier-core` - Consumer of mount plans for session creation
- Web app (UI/frontend) - Calls amplifierd APIs, manages settings, visualizes mount plans
- amplifier-app-cli - Separate terminal tool (not modified, reference only)

---

## 3. Implementation Plan

**Overview**: This implementation is divided into 4 phases, delivering functionality incrementally:

1. **Phase 1**: Core mount plan generation (MVP) - 3 days
2. **Phase 2**: Persistence & querying - 2 days
3. **Phase 3**: Sub-sessions & delegation - 1.5 days
4. **Phase 4**: Validation & health checks - 1 day

**Total**: ~7.5 days (47 hours)

**What's NOT Included**: Terminal-based settings hierarchy (CLI flags, config files, environment variables). The web app handles settings management and passes final values to amplifierd via `settings_overrides` in API requests.

---

### Phase 1: Core Mount Plan Generation (Week 1) 🎯

**Goal**: Generate mount plans from cached profiles with basic structure.

**Priority**: CRITICAL - Foundation for all other phases

#### 3.1.1 Create Data Models

**File**: `amplifierd/models/mount_plans.py`

**Models to Implement**:

**CRITICAL DESIGN NOTE**: Based on analysis of amplifier-core expectations, there are TWO fundamentally different types of mounts:

1. **Embedded Mounts** (agents, context): Content embedded as TEXT in mount plan
2. **Referenced Mounts** (providers, tools, hooks): File paths for runtime loading

```python
from typing import Literal, Union
from pydantic import BaseModel, Field

class EmbeddedMount(BaseModel):
    """For agents and context - content embedded in mount plan for LLM consumption"""
    mount_type: Literal["embedded"] = "embedded"
    module_id: str          # Unique ID: {profile}.{type}.{name}
    module_type: Literal["agent", "context"]
    content: str            # Full markdown/text content (NOT a file path)
    metadata: dict[str, Any] = Field(default_factory=dict)

class ReferencedMount(BaseModel):
    """For code modules - path reference for runtime loading"""
    mount_type: Literal["referenced"] = "referenced"
    module_id: str          # Unique ID: {profile}.{type}.{name}
    module_type: Literal["provider", "tool", "hook"]
    source_path: str        # file:// URL to cached module
    metadata: dict[str, Any] = Field(default_factory=dict)

# Union type for type safety (Pydantic discriminates on mount_type)
MountPoint = Union[EmbeddedMount, ReferencedMount]

class SessionConfig(BaseModel):
    """Session configuration and metadata."""
    session_id: str
    profile_id: str
    parent_session_id: str | None
    settings: dict[str, Any]
    created_at: str

class MountPlan(BaseModel):
    """Complete mount plan for a session."""
    session: SessionConfig
    mount_points: list[MountPoint]

    # Organized views (computed from mount_points)
    orchestrator: dict[str, Any] | None
    context: dict[str, MountPoint]
    agents: dict[str, MountPoint]
    profiles: dict[str, MountPoint]
    providers: dict[str, MountPoint]
    tools: dict[str, MountPoint]
    hooks: dict[str, MountPoint]

    def _organize_mount_points(self) -> None:
        """Group mount points by module type."""
        # Implementation in model_post_init

class MountPlanRequest(BaseModel):
    """Request to generate a mount plan."""
    profile_id: str
    session_id: str | None
    parent_session_id: str | None
    settings_overrides: dict[str, Any]
    agent_overlay: dict[str, Any] | None

class MountPlanSummary(BaseModel):
    """Lightweight summary for listing."""
    session_id: str
    profile_id: str
    created_at: str
    mount_point_count: int
    module_types: dict[str, int]
```

**Acceptance Criteria**:
- [ ] All models have proper docstrings
- [ ] Pydantic validation works correctly
- [ ] `MountPlan._organize_mount_points()` groups by type
- [ ] Models follow camelCase convention (via `CamelCaseModel`)
- [ ] Unit tests for model validation

**Time Estimate**: 4 hours

---

#### 3.1.1.1 Understanding the Mounting Mechanism

**Why Two Different Mount Types?**

Based on analysis of amplifier-app-cli and amplifier-core integration:

**Agents and Context** (Embedded):
- **Purpose**: System instructions for LLMs (markdown text)
- **Consumption**: Must be TEXT that LLM can process
- **Mounting**: Content embedded directly in mount plan
- **Why**: LLMs need actual text, not file paths
- **Example**: `{"content": "# Agent\n\nYou are a researcher..."}`

**Providers, Tools, Hooks** (Referenced):
- **Purpose**: Executable Python modules
- **Consumption**: Loaded at runtime by module resolver
- **Mounting**: File path/URL for dynamic loading
- **Why**: Code loading happens at runtime, not compile time
- **Example**: `{"source_path": "file:///path/to/provider.py"}`

**Path Format**: Use `file://` URLs for consistency and clarity
```python
# Absolute file:// URL to cached resource
"file:///home/user/.amplifierd/share/profiles/foundation/base/agents/zen-architect.md"
```

**When Embedding Happens**:
- At profile compilation time (once per profile)
- Profile service reads cached files and extracts content
- Content stored in mount plan, ready for LLM consumption

**When Referencing Happens**:
- For Python modules that execute at runtime
- Path points to cached file in share dir
- Consumer (amplifier-core) loads module when needed

---

#### 3.1.2 Create MountPlanService

**File**: `amplifierd/services/mount_plan_service.py`

**Core Methods**:
```python
class MountPlanService:
    def __init__(
        self,
        profile_service: ProfileService,
        ref_service: RefResolutionService,
    ):
        self.profile_service = profile_service
        self.ref_service = ref_service
        self.share_dir = get_share_dir()

    async def generate_mount_plan(
        self,
        request: MountPlanRequest
    ) -> MountPlan:
        """Generate mount plan from cached profile."""
        # 1. Get cached profile details
        # 2. Generate session ID (if not provided)
        # 3. Create session config
        # 4. Convert manifest resources to mount points
        # 5. Return organized mount plan

    def _create_mount_point(
        self,
        resource: dict,
        profile_dir: Path,
        profile_id: str,
    ) -> MountPoint:
        """Convert manifest resource to mount point (embedded or referenced)."""
        # 1. Construct module_id: {profile_id}.{type}.{name}
        # 2. Find resource file in cache
        # 3. Determine if should embed or reference
        # 4. Return EmbeddedMount or ReferencedMount

        resource_type = resource["type"]
        resource_name = resource["name"]
        module_id = f"{profile_id}.{resource_type}.{resource_name}"

        # Find resource file
        resource_path = self._find_resource_file(
            profile_dir, resource_type, resource_name
        )

        if resource_type in ["agent", "context"]:
            # EMBED: Read content and create EmbeddedMount
            content = resource_path.read_text(encoding="utf-8")
            return EmbeddedMount(
                module_id=module_id,
                module_type=resource_type,
                content=content,
                metadata=resource.get("metadata", {})
            )
        else:
            # REFERENCE: Create file:// URL and ReferencedMount
            abs_path = resource_path.resolve()
            file_url = f"file://{abs_path}"
            return ReferencedMount(
                module_id=module_id,
                module_type=resource_type,
                source_path=file_url,
                metadata=resource.get("metadata", {})
            )

    def _find_resource_file(
        self,
        profile_dir: Path,
        resource_type: str,
        name: str,
    ) -> Path:
        """Find resource file with flexible matching."""
        # Try: {name}.md, {name}.yaml, {name}.py, {name}/main.md
```

**Key Implementation Details**:
1. **Module ID Convention**: `{profile_id}.{resource_type}.{resource_name}`
   - Example: `foundation/base.agents.zen-architect`
2. **Resource Discovery**: Check multiple file patterns (`.md`, `.yaml`, `.py`, subdirs)
3. **Content Reading**: UTF-8 encoding, handle YAML frontmatter if present
4. **Error Handling**: Raise `ValueError` for missing profiles, `FileNotFoundError` for missing resources

**Acceptance Criteria**:
- [ ] `generate_mount_plan()` creates valid `MountPlan` from cached profile
- [ ] Module IDs follow convention
- [ ] All resource types handled (agents, context, modules)
- [ ] Missing profiles raise clear errors
- [ ] Missing resources raise clear errors
- [ ] Unit tests for service methods

**Time Estimate**: 8 hours

---

#### 3.1.3 Create API Router

**File**: `amplifierd/routers/mount_plans.py`

**Endpoints**:
```python
@router.post("/generate", response_model=MountPlan)
async def generate_mount_plan(
    request: MountPlanRequest,
    service: MountPlanService = Depends(get_mount_plan_service),
) -> MountPlan:
    """Generate mount plan from cached profile."""

@router.get("/{session_id}", response_model=MountPlan)
async def get_mount_plan(
    session_id: str,
    service: MountPlanService = Depends(get_mount_plan_service),
) -> MountPlan:
    """Retrieve previously generated mount plan (Phase 2)."""

@router.get("/", response_model=list[MountPlanSummary])
async def list_mount_plans(
    profile_id: str | None = None,
    parent_session_id: str | None = None,
    service: MountPlanService = Depends(get_mount_plan_service),
) -> list[MountPlanSummary]:
    """List mount plans with filters (Phase 2)."""

@router.post("/{session_id}/sub-session", response_model=MountPlan)
async def create_sub_session(
    session_id: str,
    agent_overlay: dict,
    settings_overrides: dict | None = None,
    service: MountPlanService = Depends(get_mount_plan_service),
) -> MountPlan:
    """Create sub-session with agent overlay (Phase 3)."""
```

**Error Handling**:
- 404 for missing profiles/sessions
- 400 for invalid requests
- 500 for server errors (with details)

**Acceptance Criteria**:
- [ ] POST `/generate` works with valid profile
- [ ] 404 returned for missing profile
- [ ] Response matches `MountPlan` schema
- [ ] Error messages are clear and actionable
- [ ] Integration tests for happy path and errors

**Time Estimate**: 4 hours

---

#### 3.1.4 Wire Up Dependencies

**File**: `amplifierd/dependencies.py`

**Add**:
```python
from amplifierd.services.mount_plan_service import MountPlanService

def get_mount_plan_service() -> MountPlanService:
    """Dependency injection for MountPlanService."""
    return MountPlanService(
        profile_service=get_profile_service(),
        ref_service=get_ref_resolution_service(),
    )
```

**File**: `amplifierd/main.py`

**Register Router**:
```python
from amplifierd.routers import mount_plans

app.include_router(mount_plans.router)
```

**Acceptance Criteria**:
- [ ] Service instantiates correctly
- [ ] Router registered with FastAPI app
- [ ] Swagger docs show new endpoints
- [ ] Health check passes

**Time Estimate**: 1 hour

---

#### 3.1.5 Write Tests

**Files**:
- `tests/models/test_mount_plans.py` - Model validation tests
- `tests/services/test_mount_plan_service.py` - Service unit tests
- `tests/routers/test_mount_plans.py` - API integration tests

**Test Coverage**:
1. **Model Tests**:
   - Validation of all fields
   - `_organize_mount_points()` logic
   - Edge cases (empty lists, missing fields)

2. **Service Tests**:
   - `generate_mount_plan()` with valid profile
   - Error handling for missing profile
   - Error handling for missing resources
   - Module ID convention
   - Resource file discovery

3. **API Tests**:
   - POST `/generate` happy path
   - 404 for missing profile
   - Response schema validation
   - Multiple resource types

**Acceptance Criteria**:
- [ ] 90%+ code coverage
- [ ] All edge cases covered
- [ ] Tests run in CI/CD
- [ ] Tests pass consistently

**Time Estimate**: 6 hours

---

#### Phase 1 Summary

**Total Time**: ~23 hours (~3 days)

**Deliverables**:
- ✅ Data models for mount plans
- ✅ Service to generate mount plans
- ✅ API endpoint: POST `/api/v1/mount-plans/generate`
- ✅ Full test coverage
- ✅ Documentation

**Validation**:
```bash
# 1. Cache a profile
curl -X POST http://localhost:8000/api/v1/collections/sync \
  -H "Content-Type: application/json" \
  -d '{"collection_id": "foundation"}'

# 2. Generate mount plan
curl -X POST http://localhost:8000/api/v1/mount-plans/generate \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "foundation/base",
    "settings_overrides": {"llm": {"model": "gpt-4"}}
  }' | jq

# Expected output:
# {
#   "session": {
#     "session_id": "session_abc123",
#     "profile_id": "foundation/base",
#     "settings": {"llm": {"model": "gpt-4"}},
#     "created_at": "2025-01-25T10:00:00Z"
#   },
#   "mount_points": [
#     {
#       "mount_type": "embedded",
#       "module_id": "foundation/base.agents.zen-architect",
#       "module_type": "agent",
#       "content": "# Zen Architect\n\nYou are a software architect...",
#       "metadata": {}
#     },
#     {
#       "mount_type": "referenced",
#       "module_id": "foundation/base.providers.anthropic",
#       "module_type": "provider",
#       "source_path": "file:///home/user/.amplifierd/share/profiles/foundation/base/providers/anthropic.py",
#       "metadata": {}
#     },
#     {
#       "mount_type": "embedded",
#       "module_id": "foundation/base.context.implementation-philosophy",
#       "module_type": "context",
#       "content": "# Implementation Philosophy\n\nThis document outlines...",
#       "metadata": {}
#     }
#   ],
#   "agents": {
#     "foundation/base.agents.zen-architect": {...}
#   },
#   "providers": {
#     "foundation/base.providers.anthropic": {...}
#   },
#   "context": {
#     "foundation/base.context.implementation-philosophy": {...}
#   }
# }
```

---

### Phase 2: Session State & Persistence (Week 2) 📦

**Goal**: Implement complete session lifecycle management with persistence.

**Priority**: HIGH - Enables session lifecycle management

**Scope**: This phase extends beyond just mount plans to include full session state tracking (status, transcripts, metadata).

#### 3.2.1 Design Storage Structure

**Location**: `.amplifierd/state/sessions/`

**Complete Structure**:
```
.amplifierd/state/sessions/
  session_abc123/
    mount_plan.json       # Full MountPlan (EmbeddedMount + ReferencedMount)
    session.json          # SessionMetadata (status, timestamps, metrics)
    transcript.jsonl      # SessionMessage per line (append-only)
  session_def456/
    mount_plan.json
    session.json
    transcript.jsonl
  index.json              # SessionIndex (fast lookups)
```

**File Purposes**:

| File | Content | Format | Update Pattern |
|------|---------|--------|----------------|
| `mount_plan.json` | MountPlan with all mounts | JSON | Write once on creation |
| `session.json` | SessionMetadata (status, timestamps) | JSON | Atomic updates (tmp + rename) |
| `transcript.jsonl` | Messages (one per line) | JSONL | Append-only |
| `index.json` | SessionIndex (all sessions) | JSON | Rebuild on any session change |

**Session State Model**:
```python
class SessionStatus(str, Enum):
    CREATED = "created"      # Mount plan generated
    ACTIVE = "active"        # Session running
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"        # Error occurred
    TERMINATED = "terminated" # User killed

class SessionMetadata(BaseModel):
    session_id: str
    parent_session_id: str | None
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    profile_name: str
    mount_plan_path: str     # Reference to mount_plan.json
    message_count: int = 0
    agent_invocations: int = 0
    token_usage: int | None = None
    error_message: str | None = None
    error_details: dict | None = None

class SessionMessage(BaseModel):
    timestamp: datetime
    role: str  # "user" | "assistant" | "system"
    content: str
    agent: str | None = None
    token_count: int | None = None
```

**Index Schema**:
```json
{
  "sessions": {
    "session_abc123": {
      "session_id": "session_abc123",
      "status": "active",
      "profile_name": "foundation/base",
      "created_at": "2025-01-25T10:00:00Z",
      "message_count": 5
    }
  }
}
```

**State Transitions**:
```
CREATED → ACTIVE → (COMPLETED | FAILED | TERMINATED)
```

**Acceptance Criteria**:
- [ ] Directory structure documented
- [ ] All data models defined
- [ ] State transition rules clear
- [ ] Atomic write operations
- [ ] Append-only transcript pattern
- [ ] Index update strategy

**Time Estimate**: 3 hours

---

#### 3.2.2 Implement SessionStateService

**New File**: `amplifierd/services/session_state_service.py`

**Core Service**:
```python
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import shutil

from amplifierd.models.sessions import (
    SessionMetadata, SessionMessage, SessionStatus,
    SessionIndex, SessionIndexEntry
)

class SessionStateService:
    """Manages session lifecycle and persistence."""

    def __init__(self, state_dir: Path):
        self.sessions_dir = state_dir / "sessions"
        self.index_path = self.sessions_dir / "index.json"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # --- Lifecycle Management ---

    def create_session(
        self,
        session_id: str,
        profile_name: str,
        mount_plan_path: str,
        parent_session_id: Optional[str] = None
    ) -> SessionMetadata:
        """Create new session in CREATED state."""
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        metadata = SessionMetadata(
            session_id=session_id,
            parent_session_id=parent_session_id,
            status=SessionStatus.CREATED,
            created_at=datetime.now(),
            profile_name=profile_name,
            mount_plan_path=mount_plan_path
        )

        # Write session.json
        (session_dir / "session.json").write_text(
            metadata.model_dump_json(indent=2)
        )

        # Create empty transcript
        (session_dir / "transcript.jsonl").touch()

        # Update index
        self._update_index(metadata)

        return metadata

    def start_session(self, session_id: str) -> None:
        """Transition CREATED → ACTIVE."""
        def update(metadata: SessionMetadata):
            metadata.status = SessionStatus.ACTIVE
            metadata.started_at = datetime.now()
        self._update_session(session_id, update)

    def complete_session(self, session_id: str) -> None:
        """Transition ACTIVE → COMPLETED."""
        def update(metadata: SessionMetadata):
            metadata.status = SessionStatus.COMPLETED
            metadata.ended_at = datetime.now()
        self._update_session(session_id, update)

    def fail_session(
        self,
        session_id: str,
        error_message: str,
        error_details: Optional[dict] = None
    ) -> None:
        """Transition ACTIVE → FAILED."""
        def update(metadata: SessionMetadata):
            metadata.status = SessionStatus.FAILED
            metadata.ended_at = datetime.now()
            metadata.error_message = error_message
            metadata.error_details = error_details
        self._update_session(session_id, update)

    # --- Transcript Management ---

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: Optional[str] = None,
        token_count: Optional[int] = None
    ) -> None:
        """Append message to transcript (efficient append-only)."""
        transcript_path = self.sessions_dir / session_id / "transcript.jsonl"

        message = SessionMessage(
            timestamp=datetime.now(),
            role=role,
            content=content,
            agent=agent,
            token_count=token_count
        )

        # Append to JSONL
        with open(transcript_path, "a") as f:
            f.write(message.model_dump_json() + "\n")

        # Update counts in metadata
        def update(metadata: SessionMetadata):
            metadata.message_count += 1
            if token_count:
                metadata.token_usage = (metadata.token_usage or 0) + token_count
        self._update_session(session_id, update)

    def get_transcript(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> list[SessionMessage]:
        """Read transcript (optionally limited to last N messages)."""
        transcript_path = self.sessions_dir / session_id / "transcript.jsonl"

        if not transcript_path.exists():
            return []

        messages = []
        with open(transcript_path) as f:
            for line in f:
                if line.strip():
                    messages.append(SessionMessage.model_validate_json(line))

        # Return last N if limited
        if limit:
            return messages[-limit:]
        return messages

    # --- Helpers ---

    def _update_session(
        self,
        session_id: str,
        update_fn: Callable[[SessionMetadata], None]
    ) -> None:
        """Atomically update session metadata."""
        session_path = self.sessions_dir / session_id / "session.json"

        # Read
        with open(session_path) as f:
            metadata = SessionMetadata.model_validate_json(f.read())

        # Modify
        update_fn(metadata)

        # Write atomically (tmp + rename)
        tmp_path = session_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))
        tmp_path.rename(session_path)

        # Update index
        self._update_index(metadata)
```

**Acceptance Criteria**:
- [ ] SessionStateService created
- [ ] All lifecycle methods implemented
- [ ] Atomic updates work correctly
- [ ] Transcript append is efficient
- [ ] Index stays consistent
- [ ] State transitions validated
- [ ] Tests for all methods

**Time Estimate**: 8 hours

---

#### 3.2.3 Add Query and Cleanup Methods

**Add to SessionStateService**:

```python
# --- Queries ---

def get_session(self, session_id: str) -> SessionMetadata | None:
    """Get session metadata by ID."""
    session_path = self.sessions_dir / session_id / "session.json"
    if not session_path.exists():
        return None
    return SessionMetadata.model_validate_json(session_path.read_text())

def list_sessions(
    self,
    status: Optional[SessionStatus] = None,
    profile_name: Optional[str] = None,
    since: Optional[datetime] = None
) -> list[SessionMetadata]:
    """Query sessions with filters."""
    index = self._load_index()
    results = []

    for session_id, entry in index.sessions.items():
        # Apply filters
        if status and entry.status != status:
            continue
        if profile_name and entry.profile_name != profile_name:
            continue
        if since and entry.created_at < since:
            continue

        # Load full metadata
        metadata = self.get_session(session_id)
        if metadata:
            results.append(metadata)

    return results

def get_active_sessions(self) -> list[SessionMetadata]:
    """Get all ACTIVE sessions."""
    return self.list_sessions(status=SessionStatus.ACTIVE)

# --- Cleanup ---

def delete_session(self, session_id: str) -> bool:
    """Delete session directory and remove from index."""
    session_dir = self.sessions_dir / session_id
    if not session_dir.exists():
        return False

    # Remove directory
    shutil.rmtree(session_dir)

    # Update index
    index = self._load_index()
    if session_id in index.sessions:
        del index.sessions[session_id]
        self._save_index(index)

    return True

def cleanup_old_sessions(
    self,
    older_than_days: int = 30,
    keep_statuses: set[SessionStatus] = {SessionStatus.ACTIVE}
) -> int:
    """Remove sessions older than threshold (except protected statuses)."""
    cutoff = datetime.now() - timedelta(days=older_than_days)
    removed = 0

    for session_id, entry in self._load_index().sessions.items():
        # Skip protected statuses
        if entry.status in keep_statuses:
            continue

        # Check age (use ended_at if available, else created_at)
        check_date = entry.ended_at or entry.created_at
        if check_date > cutoff:
            continue

        # Delete session
        if self.delete_session(session_id):
            removed += 1

    return removed
```

**Acceptance Criteria**:
- [ ] Get session by ID works
- [ ] List sessions with filters works
- [ ] Get active sessions works
- [ ] Delete session removes all files
- [ ] Cleanup respects age threshold
- [ ] Cleanup preserves active sessions
- [ ] Index stays consistent
- [ ] Tests for all query methods

**Time Estimate**: 4 hours

---

#### 3.2.4 Create Session State API Endpoints

**New Router**: `amplifierd/routers/sessions.py`

**Endpoints**:
```python
from fastapi import APIRouter, Depends, HTTPException
from amplifierd.models.sessions import SessionMetadata, SessionMessage, SessionStatus
from amplifierd.services.session_state_service import SessionStateService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

# --- Session Lifecycle ---

@router.post("/", response_model=SessionMetadata, status_code=201)
async def create_session(
    profile_name: str,
    parent_session_id: str | None = None,
    service: SessionStateService = Depends(get_session_state_service)
) -> SessionMetadata:
    """Create new session with mount plan."""
    # This will integrate with MountPlanService

@router.post("/{session_id}/start", status_code=204)
async def start_session(
    session_id: str,
    service: SessionStateService = Depends(get_session_state_service)
) -> None:
    """Start session (CREATED → ACTIVE)."""
    service.start_session(session_id)

@router.post("/{session_id}/complete", status_code=204)
async def complete_session(
    session_id: str,
    service: SessionStateService = Depends(get_session_state_service)
) -> None:
    """Complete session (ACTIVE → COMPLETED)."""
    service.complete_session(session_id)

@router.post("/{session_id}/fail", status_code=204)
async def fail_session(
    session_id: str,
    error_message: str,
    error_details: dict | None = None,
    service: SessionStateService = Depends(get_session_state_service)
) -> None:
    """Mark session as failed."""
    service.fail_session(session_id, error_message, error_details)

# --- Queries ---

@router.get("/{session_id}", response_model=SessionMetadata)
async def get_session(
    session_id: str,
    service: SessionStateService = Depends(get_session_state_service)
) -> SessionMetadata:
    """Get session metadata."""
    metadata = service.get_session(session_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Session not found")
    return metadata

@router.get("/", response_model=list[SessionMetadata])
async def list_sessions(
    status: SessionStatus | None = None,
    profile_name: str | None = None,
    service: SessionStateService = Depends(get_session_state_service)
) -> list[SessionMetadata]:
    """List sessions with filters."""
    return service.list_sessions(status=status, profile_name=profile_name)

@router.get("/active", response_model=list[SessionMetadata])
async def get_active_sessions(
    service: SessionStateService = Depends(get_session_state_service)
) -> list[SessionMetadata]:
    """Get all active sessions."""
    return service.get_active_sessions()

# --- Transcripts ---

@router.get("/{session_id}/transcript", response_model=list[SessionMessage])
async def get_transcript(
    session_id: str,
    limit: int | None = None,
    service: SessionStateService = Depends(get_session_state_service)
) -> list[SessionMessage]:
    """Get session transcript (optionally limited to last N messages)."""
    return service.get_transcript(session_id, limit=limit)

@router.post("/{session_id}/messages", status_code=201)
async def append_message(
    session_id: str,
    role: str,
    content: str,
    agent: str | None = None,
    token_count: int | None = None,
    service: SessionStateService = Depends(get_session_state_service)
) -> None:
    """Append message to session transcript."""
    service.append_message(
        session_id=session_id,
        role=role,
        content=content,
        agent=agent,
        token_count=token_count
    )

# --- Management ---

@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    service: SessionStateService = Depends(get_session_state_service)
) -> None:
    """Delete session and all its data."""
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

@router.post("/cleanup", response_model=dict)
async def cleanup_old_sessions(
    older_than_days: int = 30,
    service: SessionStateService = Depends(get_session_state_service)
) -> dict:
    """Cleanup old sessions."""
    removed = service.cleanup_old_sessions(older_than_days=older_than_days)
    return {"removed_count": removed}
```

**Acceptance Criteria**:
- [ ] All lifecycle endpoints work
- [ ] All query endpoints work
- [ ] Transcript append/retrieve works
- [ ] Delete removes all files
- [ ] Cleanup respects filters
- [ ] 404 for missing sessions
- [ ] Integration tests for all endpoints

**Time Estimate**: 4 hours

---

#### Phase 2 Summary

**Total Time**: ~19 hours (~2.5 days)

**Deliverables**:
- ✅ Complete session state models (SessionMetadata, SessionMessage, SessionStatus)
- ✅ SessionStateService for lifecycle management
- ✅ Mount plan persistence integrated with session state
- ✅ Append-only transcript storage (JSONL)
- ✅ Fast index for queries
- ✅ Session lifecycle API (create, start, complete, fail, terminate)
- ✅ Transcript API (append messages, retrieve transcript)
- ✅ Query API (list sessions, filter by status/profile)
- ✅ Cleanup utilities (age-based with status protection)
- ✅ Full session management system

**Validation**:
```bash
# Create session (generates mount plan + creates session state)
SESSION_ID=$(curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "foundation/base"}' | jq -r '.session_id')

# Start session
curl -X POST http://localhost:8000/api/v1/sessions/$SESSION_ID/start

# Append messages to transcript
curl -X POST http://localhost:8000/api/v1/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "Hello Claude"}'

# Get session metadata
curl http://localhost:8000/api/v1/sessions/$SESSION_ID | jq

# Get transcript
curl http://localhost:8000/api/v1/sessions/$SESSION_ID/transcript | jq

# List all active sessions
curl http://localhost:8000/api/v1/sessions/active | jq

# Complete session
curl -X POST http://localhost:8000/api/v1/sessions/$SESSION_ID/complete

# List completed sessions
curl "http://localhost:8000/api/v1/sessions/?status=completed" | jq

# Cleanup old sessions (>30 days)
curl -X POST "http://localhost:8000/api/v1/sessions/cleanup?older_than_days=30" | jq

# Delete specific session
curl -X DELETE http://localhost:8000/api/v1/sessions/$SESSION_ID
```

---

### Phase 3: Sub-Sessions & Delegation (Week 3) 🔀

**Goal**: Support session delegation with agent overlays.

**Priority**: MEDIUM - Enables advanced session patterns

#### 3.3.1 Implement Overlay Merging

**Add to Service**:
```python
async def create_sub_session(
    self,
    parent_session_id: str,
    agent_overlay: dict[str, Any],
    settings_overrides: dict[str, Any] | None = None,
) -> MountPlan:
    """Create a sub-session with agent customizations."""
    # 1. Load parent mount plan
    parent_plan = await self.get_mount_plan(parent_session_id)
    if not parent_plan:
        raise ValueError(f"Parent session not found: {parent_session_id}")

    # 2. Create sub-session request
    request = MountPlanRequest(
        profile_id=parent_plan.session.profile_id,
        parent_session_id=parent_session_id,
        settings_overrides=settings_overrides or {},
        agent_overlay=agent_overlay,
    )

    # 3. Generate new plan with overlays
    sub_plan = await self.generate_mount_plan(request)

    # 4. Apply agent overlays (merge with parent)
    sub_plan = self._merge_agent_overlays(sub_plan, parent_plan, agent_overlay)

    return sub_plan

def _merge_agent_overlays(
    self,
    sub_plan: MountPlan,
    parent_plan: MountPlan,
    overlay: dict[str, Any],
) -> MountPlan:
    """Merge agent overlays into sub-session plan."""
    # Deep merge logic: parent config + overlay config
    # Handle: enabled/disabled, config updates, new agents
```

**Acceptance Criteria**:
- [ ] Sub-sessions link to parent
- [ ] Agent overlays merge correctly
- [ ] Settings inheritance works
- [ ] Can override enabled/disabled state
- [ ] Can add new agents not in parent
- [ ] Tests for overlay merging

**Time Estimate**: 6 hours

---

#### 3.3.2 Update API Endpoint

**Enable**: POST `/api/v1/mount-plans/{session_id}/sub-session`

**Request Body**:
```json
{
  "agent_overlay": {
    "agents": {
      "bug-hunter": {
        "enabled": true,
        "config": {"verbose": true}
      }
    }
  },
  "settings_overrides": {
    "session": {"timeout": 3600}
  }
}
```

**Acceptance Criteria**:
- [ ] Endpoint creates sub-session
- [ ] Returns new session ID
- [ ] Links to parent in response
- [ ] Integration tests

**Time Estimate**: 2 hours

---

#### 3.3.3 Document Delegation Patterns

**Add to Docs**:
- Common delegation use cases
- Agent overlay syntax
- Best practices for sub-sessions
- Examples with multiple levels

**Acceptance Criteria**:
- [ ] Documentation complete
- [ ] Examples tested
- [ ] Patterns documented

**Time Estimate**: 3 hours

---

#### Phase 3 Summary

**Total Time**: ~11 hours (~1.5 days)

**Deliverables**:
- ✅ Sub-session creation with overlays
- ✅ Agent overlay merging logic
- ✅ Parent-child session linking
- ✅ API endpoint for delegation
- ✅ Documentation and examples

**Validation**:
```bash
# Create parent session
PARENT_ID=$(curl -X POST http://localhost:8000/api/v1/mount-plans/generate \
  -H "Content-Type: application/json" \
  -d '{"profile_id": "foundation/base"}' | jq -r '.session.session_id')

# Create sub-session with specialized agent
curl -X POST http://localhost:8000/api/v1/mount-plans/$PARENT_ID/sub-session \
  -H "Content-Type: application/json" \
  -d '{
    "agent_overlay": {
      "agents": {
        "bug-hunter": {
          "enabled": true,
          "config": {"verbose": true}
        }
      }
    },
    "settings_overrides": {
      "session": {"timeout": 3600}
    }
  }' | jq
```

---

### Phase 4: Validation & Health (Week 4) ✅

**Goal**: Ensure mount plans are valid and complete.

**Priority**: MEDIUM - Quality assurance

**Note**: This phase focuses on mount plan validation and API health checks. We are NOT implementing settings hierarchy (that was removed - web app handles settings).

#### 4.1 Mount Plan Validation

**Add to Service**:
```python
async def validate_mount_plan(self, plan: MountPlan) -> dict[str, list[str]]:
    """
    Validate mount plan for completeness and correctness.

    Returns dict of validation errors by category:
    - "missing_resources": Resources referenced but not found
    - "duplicate_ids": Module IDs that appear multiple times
    - "invalid_config": Configuration issues
    """
    errors = {
        "missing_resources": [],
        "duplicate_ids": [],
        "invalid_config": []
    }

    # Check for missing resources
    for mount_point in plan.mount_points:
        if not Path(mount_point.source_path).exists():
            errors["missing_resources"].append(
                f"{mount_point.module_id}: {mount_point.source_path}"
            )

    # Check for duplicate module IDs
    seen_ids = set()
    for mount_point in plan.mount_points:
        if mount_point.module_id in seen_ids:
            errors["duplicate_ids"].append(mount_point.module_id)
        seen_ids.add(mount_point.module_id)

    # Remove empty error categories
    return {k: v for k, v in errors.items() if v}
```

**API Endpoint**:
```python
@router.post("/validate", response_model=dict[str, list[str]])
async def validate_mount_plan_endpoint(
    plan: MountPlan,
    service: MountPlanService = Depends(get_mount_plan_service),
) -> dict[str, list[str]]:
    """Validate a mount plan for errors."""
    return await service.validate_mount_plan(plan)
```

**Acceptance Criteria**:
- [ ] Detects missing resource files
- [ ] Detects duplicate module IDs
- [ ] Validates configuration structure
- [ ] Returns clear error messages
- [ ] Tests for validation logic

**Time Estimate**: 4 hours

---

#### 4.2 Health Check Endpoint

**Add Endpoint**:
```python
@router.get("/health")
async def health_check(
    service: MountPlanService = Depends(get_mount_plan_service),
) -> dict[str, Any]:
    """Health check for mount plan service."""
    return {
        "status": "healthy",
        "service": "mount_plan_service",
        "storage_available": service.state_dir.exists(),
        "cache_available": service.share_dir.exists()
    }
```

**Acceptance Criteria**:
- [ ] Returns service health status
- [ ] Checks storage availability
- [ ] Checks cache availability
- [ ] Always returns 200 (even if degraded)

**Time Estimate**: 1 hour

---

#### Phase 4 Summary

**Total Time**: ~5 hours (~1 day with buffer)

**Deliverables**:
- ✅ Mount plan validation logic
- ✅ Validation API endpoint
- ✅ Health check endpoint
- ✅ Error detection for common issues

**Validation**:
```bash
# Validate a mount plan
curl -X POST http://localhost:8000/api/v1/mount-plans/validate \
  -H "Content-Type: application/json" \
  -d @mount_plan.json | jq

# Health check
curl http://localhost:8000/api/v1/mount-plans/health | jq
```

---

## 4. Testing Strategy

### 4.1 Unit Tests

**Coverage**:
- All Pydantic models (validation, defaults)
- All service methods (happy path + errors)
- Resource file discovery logic
- Module ID generation
- Overlay merging

**Frameworks**:
- `pytest` for test execution
- `pytest-asyncio` for async tests
- `httpx` for API client tests

### 4.2 Integration Tests

**Scenarios**:
1. End-to-end: Sync profile → generate plan → verify structure
2. Persistence: Generate → save → retrieve → compare
3. Sub-sessions: Parent → child → verify inheritance
4. Error cases: Missing profile, missing resources, invalid overlays

### 4.3 Manual Testing

**Checklist**:
- [ ] Generate plan for `foundation/base` profile
- [ ] Verify all agents appear in `mount_plan.agents`
- [ ] Verify all context appears in `mount_plan.context`
- [ ] Create sub-session and verify parent link
- [ ] List plans and verify filtering
- [ ] Delete plan and verify removal

### 4.4 Performance Testing

**Benchmarks**:
- Mount plan generation time: target < 100ms
- Mount plan retrieval time: target < 10ms
- List operation time: target < 50ms for 100 sessions

---

## 5. API Documentation

### 5.1 OpenAPI/Swagger

**Ensure**:
- All endpoints documented in Swagger UI
- Request/response examples provided
- Error responses documented
- Authentication requirements clear (if any)

### 5.2 Usage Examples

**Add to README**:
```python
# Python client example
import httpx

# Generate mount plan
response = httpx.post(
    "http://localhost:8000/api/v1/mount-plans/generate",
    json={"profile_id": "foundation/base"}
)
mount_plan = response.json()
print(f"Session ID: {mount_plan['session']['session_id']}")

# Retrieve mount plan
session_id = mount_plan['session']['session_id']
response = httpx.get(f"http://localhost:8000/api/v1/mount-plans/{session_id}")
retrieved_plan = response.json()
```

---

## 6. Success Criteria

### Phase 1 (MVP)
- [x] Design complete
- [ ] Generate mount plans from cached profiles
- [ ] Mount points contain correct content
- [ ] Module IDs follow convention
- [ ] Resources organized by type
- [ ] API responds with valid JSON
- [ ] Tests pass with 90%+ coverage

### Phase 2 (Persistence)
- [ ] Mount plans persist to disk
- [ ] Retrieval by session ID works
- [ ] Listing with filters works
- [ ] Cleanup utilities implemented
- [ ] Index stays consistent

### Phase 3 (Sub-Sessions)
- [ ] Sub-session creation works
- [ ] Agent overlays merge correctly
- [ ] Parent-child links tracked
- [ ] Settings inheritance works

### Phase 4 (Validation)
- [ ] Mount plan validation implemented
- [ ] Health check endpoint functional
- [ ] Missing resource detection works
- [ ] Configuration conflict detection works

### Overall Success
- [ ] All tests pass
- [ ] API documentation complete
- [ ] Integration with amplifier-core validated
- [ ] Performance targets met

---

## 7. Risk Analysis & Mitigation

### 7.1 Risks

**Technical Risks**:
1. **Profile schema changes**: If schema v2 evolves, mount plans may break
   - *Mitigation*: Version mount plan format, support migrations
2. **Resource file discovery**: Non-standard file names may not be found
   - *Mitigation*: Flexible discovery with fallbacks, clear error messages
3. **Concurrent access**: Multiple processes generating/modifying plans
   - *Mitigation*: File locking, atomic writes, read-only by default

**Integration Risks**:
1. **amplifier-core compatibility**: Mount plans may not match expected format
   - *Mitigation*: Use amplifier-app-cli as reference, validate against core
2. **Settings structure**: Web app may evolve settings format over time
   - *Mitigation*: Keep settings_overrides as dict[str, Any] for flexibility

**Operational Risks**:
1. **Disk space**: Many mount plans could consume significant space
   - *Mitigation*: Cleanup utilities, configurable retention policies
2. **Performance**: Large profiles with many resources could be slow
   - *Mitigation*: Lazy loading, caching, async I/O

### 7.2 Mitigation Strategies

**For Each Phase**:
1. Start with simplest implementation
2. Validate with real profiles early
3. Add complexity only when needed
4. Test error cases thoroughly
5. Document assumptions and limitations

---

## 8. Open Questions

### 8.1 Technical Questions

1. **Session lifecycle**: Should amplifierd manage active sessions or just generate plans?
   - *Current answer*: Just generate plans; let amplifier-core manage sessions
2. **Mount plan versioning**: Do we need to track plan changes over time?
   - *Current answer*: No versioning in Phase 1; add if needed later
3. **Concurrency**: How to handle concurrent plan generation for same profile?
   - *Current answer*: Allow it; plans are read-only after generation
4. **Caching**: Should we cache generated mount plans or always regenerate?
   - *Current answer*: Regenerate by default; cache is optional (Phase 2)

### 8.2 Design Questions

1. **API style**: RESTful vs RPC-style for mount plan operations?
   - *Current answer*: RESTful for CRUD, RPC-style for complex operations
2. **Module IDs**: Current convention sufficient or needs revision?
   - *Current answer*: `{profile}.{type}.{name}` is good; revisit if collisions occur
3. **Settings handling**: How should web app pass settings to daemon?
   - *Current answer*: Structured dict via `settings_overrides` - web app manages structure

### 8.3 Future Questions

1. **WebSocket support**: Real-time mount plan updates?
2. **Plan templates**: Save mount plans as reusable templates?
3. **Dependency resolution**: Auto-resolve agent/tool dependencies?
4. **Visual editor**: UI for creating/editing mount plans?

---

## 9. References

### 9.1 Related Documents

- **amplifierd Caching Analysis**: See zen-architect output (Phase 1 research)
- **amplifier-app-cli Exploration**: See Explore agent output (Phase 1 research)
- **API Architecture Design**: See zen-architect ARCHITECT mode output

### 9.2 Code References

**Existing Services**:
- `amplifierd/services/profile_service.py`
- `amplifierd/services/profile_compilation.py`
- `amplifierd/services/ref_resolution.py`
- `amplifierd/models/profiles.py`

**Reference Implementation**:
- `related-projects/amplifier-app-cli/` (session management patterns)

### 9.3 External Resources

- FastAPI documentation: https://fastapi.tiangolo.com/
- Pydantic documentation: https://docs.pydantic.dev/
- amplifier-core documentation: (link TBD)

---

## 10. Approval & Sign-off

### 10.1 Stakeholders

- [ ] **Engineering Lead** - Technical approach approved
- [ ] **Product Owner** - Requirements validated
- [ ] **Architect** - Design compliant with philosophy

### 10.2 Next Steps

1. Review this plan with team
2. Address open questions
3. Prioritize phases based on project timeline
4. Begin Phase 1 implementation
5. Schedule check-ins after each phase

---

## Appendix A: Module ID Convention

**Format**: `{profile_id}.{resource_type}.{resource_name}`

**Examples**:
- `foundation/base.agents.zen-architect`
- `foundation/base.context.implementation-philosophy`
- `developer-expertise/full.providers.openai`
- `developer-expertise/full.tools.code-interpreter`

**Rationale**:
- Globally unique across all profiles
- Self-documenting (can determine source from ID)
- Sortable and filterable by prefix
- Compatible with Python module naming

**Edge Cases**:
- Names with special characters: URL-encode or replace with underscores
- Duplicate names in same profile: Add suffix (`.2`, `.3`, etc.)
- Collection namespaces: Consider adding collection prefix if needed

---

## Appendix B: File Organization

### Before (Current State)
```
amplifierd/
  services/
    profile_service.py
    profile_compilation.py
    ref_resolution.py
  models/
    profiles.py
  routers/
    profiles.py
```

### After (Phase 1 Complete)
```
amplifierd/
  services/
    profile_service.py
    profile_compilation.py
    ref_resolution.py
    mount_plan_service.py         # NEW
  models/
    profiles.py
    mount_plans.py                # NEW
  routers/
    profiles.py
    mount_plans.py                # NEW
  dependencies.py                 # UPDATED
  main.py                         # UPDATED

tests/
  services/
    test_mount_plan_service.py    # NEW
  models/
    test_mount_plans.py           # NEW
  routers/
    test_mount_plans.py           # NEW
```

---

## Appendix C: Error Codes

**HTTP Status Codes**:
- `200 OK` - Successful retrieval
- `201 Created` - Mount plan generated
- `204 No Content` - Successful deletion
- `400 Bad Request` - Invalid request (malformed JSON, missing required fields)
- `404 Not Found` - Profile or session not found
- `500 Internal Server Error` - Server error (missing resources, I/O errors)

**Custom Error Codes** (in response body):
- `PROFILE_NOT_FOUND` - Profile not cached
- `RESOURCE_MISSING` - Expected resource file not found
- `PARENT_SESSION_NOT_FOUND` - Parent session doesn't exist
- `INVALID_OVERLAY` - Agent overlay format invalid

---

## Conclusion

This plan provides a clear path from amplifierd's current profile caching capabilities to full mount plan generation for amplifier-core. By following a phased approach with clear deliverables and success criteria, we minimize risk while enabling powerful session management features.

**Architecture Clarity**: amplifierd is the backend service for a web application. We are NOT implementing terminal-based features like config file resolution, environment variables, or CLI flag parsing. The web app manages all user-facing settings and passes finalized values to amplifierd via API requests.

**Implementation Scope**:
- **Phase 1**: Core mount plan generation (~3 days / 23 hours)
- **Phase 2**: Session state & persistence (~2.5 days / 19 hours)
- **Phase 3**: Sub-sessions & delegation (~1.5 days / 11 hours)
- **Phase 4**: Validation & health checks (~1 day / 5 hours)
- **Total**: ~8 days (58 hours) for complete implementation

**Note**: Phase 2 expanded to include full session lifecycle management (state, transcripts, queries) beyond just mount plan persistence.

**Key Takeaways**:
1. Leverage existing caching infrastructure
2. Start simple, add complexity incrementally
3. Settings hierarchy is NOT needed (web app handles this)
4. Test thoroughly at each phase
5. Validate with real profiles early

**Next Action**: Review plan with team → Begin Phase 1 implementation.
