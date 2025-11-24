# Collections and Profiles System Redesign - Implementation Plan

**Version**: 1.0
**Date**: 2025-11-24
**Author**: AI Coordinator (Claude)
**Status**: Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Overview](#design-overview)
3. [Current Architecture Analysis](#current-architecture-analysis)
4. [New Architecture Design](#new-architecture-design)
5. [Implementation Phases](#implementation-phases)
6. [Detailed Module Specifications](#detailed-module-specifications)
7. [Data Migration Strategy](#data-migration-strategy)
8. [Testing Strategy](#testing-strategy)
9. [Rollout Plan](#rollout-plan)
10. [Risk Mitigation](#risk-mitigation)
11. [Appendices](#appendices)

---

## Executive Summary

This document provides a complete implementation plan for redesigning the amplifierd daemon's collections and profiles system. The redesign fundamentally simplifies the architecture by:

- **Replacing YAML registry** with simple text file (`collection-sources.txt`)
- **Eliminating resource extraction** in favor of direct fsspec path resolution
- **Introducing explicit schema versioning** (schema v2 required)
- **Separating discovery from compilation** for profiles
- **Adding profile compilation** as an explicit step with asset caching

**Key Benefits**:
- Simpler data structures (text file vs YAML)
- Direct source access (no extraction/flattening)
- Explicit schema contracts (v2 required)
- Clearer service boundaries
- Better caching strategies

**Estimated Effort**: 4 weeks
**Breaking Changes**: Yes (requires migration)
**Backward Compatibility**: Partial (via migration script)

---

## Design Overview

### Design Goals

From the design document (`working/collections-and-profiles.md`):

1. **Simplify collection tracking**: Use text file instead of YAML registry
2. **Support flexible sources**: Git repos (`git+`) and fsspec paths
3. **Cache strategically**:
   - Git checkouts at `state/git/{commit-hash}/`
   - Profile manifests at `local/share/profiles/{collection}/{profile}.md`
   - Compiled profiles at `state/profiles/{collection}/{uid}/`
4. **Enforce schema versioning**: Only schema v2 profiles accepted
5. **Eliminate runtime inheritance**: Profiles must be fully resolved (no `extends` in daemon)

### Key Concepts

#### Collection Sources File

**Location**: `$AMPLIFIERD_ROOT/local/share/collection-sources.txt`

**Format**: One collection per line
```
<collection-id> <source-ref>
```

**Examples**:
```
foundation bundled:amplifierd.data.collections.foundation
developer-tools git+https://github.com/org/dev-tools@main
local-collection /home/user/my-collection
```

#### Profile Schema Version 2

**Requirements**:
- Must have `schema-version: 2` in YAML frontmatter
- No `extends` field (profiles fully resolved at authoring time)
- Agents referenced as individual files (not directories with patterns)
- Context referenced as directory refs (not well-known `./ai_context/`)

**Example Frontmatter**:
```yaml
---
profile:
  name: base
  schema-version: 2
  version: 1.1.0
  description: Base profile configuration

session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main

tools:
  - module: tool-web
    source: git+https://github.com/microsoft/amplifier-module-tool-web@main

agents:
  - ref: git+https://github.com/org/repo@main/agents/researcher.md
  - ref: ./local/agents/custom.md

context:
  - ref: git+https://github.com/org/repo@main/context/
---

# Profile description (markdown content)
```

#### Profile Compilation

**Purpose**: Resolve all refs and cache assets for dynamic import

**Process**:
1. Load profile manifest from cache
2. Resolve all refs (agents, context, modules)
3. Fetch/copy assets to `state/profiles/{collection}/{uid}/`
4. Create Python module structure for dynamic import
5. Return path to compiled profile directory

**Compiled Structure**:
```
state/profiles/{collection}/{profile-uid}/
  __init__.py
  orchestrator/
    __init__.py
    module.py
  context-manager/
    __init__.py
    module.py
  providers/
    __init__.py
    provider1.py
  tools/
    __init__.py
    tool1.py
  hooks/
    __init__.py
    hook1.py
  agents/
    __init__.py
    agent1.md
  context/
    __init__.py
    doc1.md
```

---

## Current Architecture Analysis

### Current Implementation

**Collection Registry**: `collections.yaml` (YAML file)
- Tracks metadata: version, source, installed_at, resources
- Full resource inventory maintained
- Complex nested structure

**Collection Storage**: Flat extraction
- Resources extracted to `{type}/{collection}/{resource}`
- All collections flattened into shared directories
- Copies made of all resources

**Profile Discovery**: Recursive scanning
- Scans `profiles/` directory recursively
- Supports `.md` (YAML frontmatter) and `.yaml` files
- One-level `extends` resolution

**Profile Activation**: Simple text file
- `active_profile.txt` stores active profile name

### Key Files and Their Roles

| File | Current Responsibility |
|------|----------------------|
| `amplifierd/models/collections.py` | API response models |
| `amplifierd/models/profiles.py` | API response models |
| `amplifierd/services/collection_registry.py` | YAML registry persistence |
| `amplifierd/services/simple_collection_service.py` | Collection mounting/extraction |
| `amplifierd/services/simple_profile_service.py` | Profile discovery/loading |
| `amplifierd/routers/collections.py` | Collection API endpoints |
| `amplifierd/routers/profiles.py` | Profile API endpoints |

### Issues with Current Design

1. **Registry complexity**: YAML parsing overhead, metadata tracking burden
2. **Resource duplication**: All collections extracted/copied
3. **Inconsistent module tracking**: All module types point to same list
4. **No caching**: Registry loaded/parsed on every operation
5. **Silent failures**: Profile `extends` failures degrade silently
6. **No schema versioning**: Profile format not validated

---

## New Architecture Design

### Directory Structure

```
$AMPLIFIERD_ROOT/
├── local/
│   └── share/
│       ├── collection-sources.txt          # NEW: Simple text registry
│       └── profiles/                       # CHANGED: Now collection-scoped
│           └── {collection-id}/
│               └── {profile-id}.md         # Cached profile manifests
├── state/
│   ├── git/                                # NEW: Git checkouts by commit
│   │   └── {commit-hash}/
│   │       ├── profiles/
│   │       ├── agents/
│   │       └── context/
│   └── profiles/                           # NEW: Compiled profiles
│       └── {collection-id}/
│           └── {profile-uid}/              # Full resolved assets
│               ├── orchestrator/
│               ├── agents/
│               ├── context/
│               └── ...
└── data/
    └── active_profile.txt                  # Unchanged
```

### Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     ProfileService                       │
│            (Orchestration & High-Level Logic)            │
└────────────────┬────────────────────────┬────────────────┘
                 │                        │
     ┌───────────▼───────────┐ ┌─────────▼──────────────┐
     │ ProfileDiscoveryService│ │ProfileCompilationService│
     │  (Find & Cache)        │ │  (Resolve & Build)      │
     └───────────┬────────────┘ └─────────┬──────────────┘
                 │                        │
     ┌───────────▼───────────┐ ┌─────────▼──────────────┐
     │CollectionSourcesService│ │ CollectionFetchService │
     │   (Text File I/O)      │ │   (Git + Fsspec)       │
     └────────────────────────┘ └────────────────────────┘
```

### Data Flow

#### Flow 1: Add Collection

```
User: POST /api/v1/collections/
      {id: "mycoll", source: "git+https://github.com/org/repo@main"}

1. CollectionSourcesService.add_source()
   → Append "mycoll git+https://..." to collection-sources.txt

2. CollectionFetchService.fetch_collection()
   → Clone repo to state/git/{commit-hash}/

3. ProfileDiscoveryService.discover_profiles()
   → Scan state/git/{commit-hash}/profiles/*.md
   → Validate schema-version: 2
   → Cache manifests to local/share/profiles/mycoll/*.md

4. Response: {id: "mycoll", profiles_count: N}
```

#### Flow 2: Activate Profile

```
User: POST /api/v1/profiles/mycoll/myprofile/activate

1. ProfileService.get_profile()
   → Read local/share/profiles/mycoll/myprofile.md

2. ProfileCompilationService.compile_profile()
   → Resolve all refs (agents, context, modules)
   → Fetch assets
   → Cache to state/profiles/mycoll/{uid}/
   → Create Python module structure

3. ProfileService.set_active()
   → Write "mycoll/myprofile" to data/active_profile.txt

4. Response: {compiled_path: "state/profiles/mycoll/{uid}/"}
```

#### Flow 3: Sync Collections

```
User: POST /api/v1/collections/sync

For each line in collection-sources.txt:
  1. CollectionFetchService.fetch_collection()
     → Re-fetch/update collection from source

  2. ProfileDiscoveryService.discover_profiles()
     → Re-scan for profiles
     → Validate schema v2
     → Update cache

Response: {synced: [collection1, collection2], errors: []}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal**: Create new data structures and basic services

**Tasks**:
1. Create `collection-sources.txt` parser
2. Implement `CollectionSourcesService`
3. Add new paths to config (`state/git/`, `state/profiles/`)
4. Update data models (add `schema_version`, remove `extends`)
5. Write unit tests for text parser

**Deliverables**:
- `amplifierd/services/collection_sources.py`
- `amplifierd/models/collections.py` (updated)
- `amplifierd/models/profiles.py` (updated)
- `amplifierd/core/config.py` (updated paths)
- `tests/services/test_collection_sources.py`

**Success Criteria**:
- Can read/write collection-sources.txt
- Parser handles edge cases (empty lines, comments, invalid format)
- All tests pass

---

### Phase 2: Collection Fetching (Week 1-2)

**Goal**: Fetch collections from various sources

**Tasks**:
1. Implement `CollectionFetchService`
2. Git checkout logic (shallow clone, commit-based caching)
3. Fsspec path resolution
4. Update bundled collection support
5. Write unit tests (mock git operations)

**Deliverables**:
- `amplifierd/services/collection_fetch.py`
- `tests/services/test_collection_fetch.py`
- Integration tests with real git repos

**Success Criteria**:
- Can fetch `git+` refs to `state/git/{commit}/`
- Can resolve local fsspec paths
- Bundled collections still work (`bundled:` prefix)
- Commit-based caching works (no duplicate clones)

---

### Phase 3: Profile Discovery (Week 2)

**Goal**: Discover profiles from collection sources

**Tasks**:
1. Implement `ProfileDiscoveryService`
2. Schema v2 validation
3. Profile manifest caching
4. Update `SimpleProfileService` to use new discovery
5. Write discovery tests

**Deliverables**:
- `amplifierd/services/profile_discovery.py`
- `amplifierd/services/simple_profile_service.py` (updated)
- `tests/services/test_profile_discovery.py`

**Success Criteria**:
- Can discover profiles from git checkouts
- Can discover profiles from fsspec paths
- Only schema v2 profiles accepted (v1 rejected with clear error)
- Profiles cached at correct paths

---

### Phase 4: Profile Compilation (Week 3)

**Goal**: Resolve profile refs and compile assets

**Tasks**:
1. Implement `ProfileCompilationService`
2. Ref resolution logic (git, fsspec, local)
3. Asset caching to `state/profiles/`
4. Python module structure generation
5. Write compilation tests

**Deliverables**:
- `amplifierd/services/profile_compilation.py`
- `tests/services/test_profile_compilation.py`
- Integration tests with real profiles

**Success Criteria**:
- Can resolve agent refs
- Can resolve context refs
- Can resolve module refs
- Compiled profiles importable as Python modules
- Assets cached at `state/profiles/{collection}/{uid}/`

---

### Phase 5: API & CLI Updates (Week 3-4)

**Goal**: Update public interfaces

**Tasks**:
1. Update collection API endpoints
2. Update profile API endpoints
3. Add compilation status to responses
4. Update OpenAPI docs
5. Add integration tests

**Deliverables**:
- `amplifierd/routers/collections.py` (updated)
- `amplifierd/routers/profiles.py` (updated)
- `tests/integration/test_collections_api.py`
- `tests/integration/test_profiles_api.py`

**Success Criteria**:
- All API endpoints work with new design
- API responses include new fields
- OpenAPI docs accurate
- Integration tests pass

---

### Phase 6: Migration & Cleanup (Week 4)

**Goal**: Deploy migration and remove old code

**Tasks**:
1. Write migration script
2. Add migration to daemon startup
3. Add deprecation warnings
4. Remove old extraction logic
5. Remove YAML registry code
6. Update documentation

**Deliverables**:
- `amplifierd/migration/collections_v2.py`
- `amplifierd/services/collection_registry.py` (removed)
- `docs/migration_guide.md`
- Updated `README.md`

**Success Criteria**:
- Migration runs automatically on first daemon start
- No data loss during migration
- Old code removed
- Clear upgrade guide available

---

## Detailed Module Specifications

### Module 1: CollectionSourcesService

**Purpose**: Manage simple text-based collection sources registry

**File**: `amplifierd/services/collection_sources.py`

**Public Contract**:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class CollectionSource:
    """Represents a single collection source."""
    id: str
    source_ref: str

class CollectionExistsError(Exception):
    """Raised when attempting to add duplicate collection ID."""
    pass

class CollectionNotFoundError(Exception):
    """Raised when collection ID not found."""
    pass

class CollectionSourcesService:
    """
    Manages the simple text-based collection sources registry.

    Format: One line per collection
      <collection-id> <source-ref>

    Example:
      foundation bundled:amplifierd.data.collections.foundation
      myrepo git+https://github.com/org/repo@main
      local /home/user/collection
    """

    def __init__(self, sources_file: Path):
        """
        Initialize with path to collection-sources.txt.

        Args:
            sources_file: Path to collection-sources.txt
        """
        self.sources_file = sources_file

    def list_sources(self) -> List[CollectionSource]:
        """
        Read all collection sources.

        Returns:
            List of CollectionSource objects

        Errors:
            IOError if file unreadable
        """

    def add_source(self, collection_id: str, source_ref: str) -> None:
        """
        Append new collection source.

        Args:
            collection_id: Unique collection identifier
            source_ref: Source reference (git+, fsspec path, bundled:)

        Side Effects:
            Appends line to sources_file

        Errors:
            CollectionExistsError if ID already exists
            IOError if file not writable
        """

    def remove_source(self, collection_id: str) -> None:
        """
        Remove collection source.

        Args:
            collection_id: Collection identifier to remove

        Side Effects:
            Removes line from sources_file

        Errors:
            CollectionNotFoundError if ID doesn't exist
            IOError if file not writable
        """

    def get_source(self, collection_id: str) -> Optional[str]:
        """
        Get source ref for collection.

        Args:
            collection_id: Collection identifier

        Returns:
            source_ref string or None if not found
        """
```

**Implementation Details**:

```python
def _parse_line(self, line: str) -> Optional[CollectionSource]:
    """
    Parse single line from sources file.

    Format: <id> <source-ref>

    Args:
        line: Single line from file

    Returns:
        CollectionSource or None if invalid/empty/comment

    Rules:
        - Skip empty lines
        - Skip lines starting with #
        - Split on first whitespace
        - ID must be alphanumeric + hyphens + underscores
        - Source ref can be any non-whitespace string
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    parts = line.split(None, 1)  # Split on first whitespace
    if len(parts) != 2:
        logger.warning(f"Invalid line format: {line}")
        return None

    collection_id, source_ref = parts

    # Validate ID format
    if not re.match(r'^[a-zA-Z0-9_-]+$', collection_id):
        logger.warning(f"Invalid collection ID: {collection_id}")
        return None

    return CollectionSource(id=collection_id, source_ref=source_ref)

def _write_sources(self, sources: List[CollectionSource]) -> None:
    """
    Atomically write sources to file.

    Args:
        sources: List of CollectionSource objects

    Side Effects:
        Writes to sources_file atomically (write temp, rename)
    """
    temp_file = self.sources_file.with_suffix('.tmp')
    try:
        with temp_file.open('w') as f:
            for source in sources:
                f.write(f"{source.id} {source.source_ref}\n")
        temp_file.replace(self.sources_file)  # Atomic rename
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        raise
```

**Testing Requirements**:
- Parse valid lines
- Skip comments and empty lines
- Reject invalid IDs
- Add new source (duplicate check)
- Remove existing source (not found check)
- Atomic writes (temp file + rename)
- File locking/concurrent access

**Dependencies**:
- `pathlib.Path`
- `dataclasses.dataclass`
- `logging`
- `re`

---

### Module 2: CollectionFetchService

**Purpose**: Resolve collection source refs to local paths

**File**: `amplifierd/services/collection_fetch.py`

**Public Contract**:

```python
from pathlib import Path
from typing import Optional

class CollectionFetchError(Exception):
    """Raised when collection fetch fails."""
    pass

class CollectionFetchService:
    """
    Fetches collections from various sources.

    Supports:
      - git+ URLs: Clone/checkout to state/git/{commit}/
      - fsspec paths: Resolve to local path
      - bundled: paths: Resolve from package data
    """

    def __init__(self, state_dir: Path):
        """
        Initialize with state directory for git checkouts.

        Args:
            state_dir: Path to state directory (for git checkouts)
        """
        self.state_dir = state_dir
        self.git_cache_dir = state_dir / "git"
        self.git_cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_collection(self, source_ref: str) -> Path:
        """
        Resolve source ref to local path.

        Args:
            source_ref: Source reference (git+URL, fsspec path, bundled:)

        Returns:
            Path to collection root directory

        Side Effects:
            - Git clone/checkout to state/git/{commit}/
            - May download remote fsspec resources

        Errors:
            CollectionFetchError if fetch fails
        """

    def _fetch_git(self, repo_url: str, ref: str = "main") -> Path:
        """
        Clone/checkout git repo to state/git/{commit}/.

        Args:
            repo_url: Git repository URL
            ref: Git ref (branch, tag, commit)

        Returns:
            Path to state/git/{commit-hash}/

        Side Effects:
            Git clone (shallow) if not cached

        Caching Strategy:
            - Commit hash used as cache key
            - If commit hash exists, return cached path
            - Otherwise, clone and cache
        """

    def _resolve_fsspec(self, fsspec_path: str) -> Path:
        """
        Resolve fsspec path to local path.

        Args:
            fsspec_path: Fsspec path (local, s3, http, etc.)

        Returns:
            Local path (may be cached if remote)

        Side Effects:
            May download remote resources to cache
        """

    def _resolve_bundled(self, bundled_path: str) -> Path:
        """
        Resolve bundled collection path.

        Args:
            bundled_path: bundled:amplifierd.data.collections.X

        Returns:
            Path to bundled collection in package data
        """
```

**Implementation Details**:

```python
def _fetch_git(self, repo_url: str, ref: str = "main") -> Path:
    """Implementation of git fetching with caching."""
    from git import Repo
    import hashlib

    # Parse git+ URL
    # git+https://github.com/org/repo@ref
    if "@" in repo_url:
        repo_url, ref = repo_url.rsplit("@", 1)
    repo_url = repo_url.removeprefix("git+")

    # Clone to temp location to get commit hash
    temp_dir = self.git_cache_dir / f"temp_{uuid.uuid4().hex[:8]}"
    try:
        logger.info(f"Cloning {repo_url} ref={ref}")
        repo = Repo.clone_from(
            repo_url,
            temp_dir,
            branch=ref,
            depth=1  # Shallow clone for speed
        )

        commit_hash = repo.head.commit.hexsha

        # Check if already cached
        cache_dir = self.git_cache_dir / commit_hash
        if cache_dir.exists():
            logger.info(f"Using cached collection: {commit_hash}")
            shutil.rmtree(temp_dir)
            return cache_dir

        # Move to cache location
        temp_dir.rename(cache_dir)
        logger.info(f"Cached collection: {commit_hash}")
        return cache_dir

    except Exception as e:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise CollectionFetchError(f"Git fetch failed: {e}")

def _resolve_fsspec(self, fsspec_path: str) -> Path:
    """Implementation of fsspec resolution."""
    import fsspec

    # For local paths, just return
    if Path(fsspec_path).exists():
        return Path(fsspec_path).resolve()

    # For remote paths, use fsspec
    try:
        fs, path = fsspec.core.url_to_fs(fsspec_path)

        # If local, return as-is
        if isinstance(fs, fsspec.implementations.local.LocalFileSystem):
            return Path(path)

        # If remote, need to cache locally
        # (Implementation depends on fsspec backend)
        cache_dir = self.state_dir / "fsspec_cache" / fs.protocol
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Download/sync to cache
        local_path = cache_dir / Path(path).name
        fs.get(path, str(local_path), recursive=True)
        return local_path

    except Exception as e:
        raise CollectionFetchError(f"Fsspec resolution failed: {e}")
```

**Testing Requirements**:
- Git clone with commit caching
- Git clone failure handling
- Fsspec local path resolution
- Fsspec remote path caching
- Bundled path resolution
- Invalid source ref handling
- Concurrent fetch requests

**Dependencies**:
- `gitpython` (git operations)
- `fsspec` (path resolution)
- `importlib.resources` (bundled collections)
- `pathlib.Path`
- `logging`

---

### Module 3: ProfileDiscoveryService

**Purpose**: Discover and cache profile manifests from collections

**File**: `amplifierd/services/profile_discovery.py`

**Public Contract**:

```python
from pathlib import Path
from typing import List
from pydantic import BaseModel

class ProfileManifest(BaseModel):
    """Profile manifest with schema v2."""
    name: str
    schema_version: int
    version: str
    description: str
    # ... other fields from profile YAML

class ProfileValidationError(Exception):
    """Raised when profile fails validation."""
    pass

class ProfileDiscoveryService:
    """
    Discovers profiles from collection sources.

    Scans collection directories for schema v2 profiles and caches manifests.
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize with profile cache directory.

        Args:
            cache_dir: Path to local/share/profiles/
        """
        self.cache_dir = cache_dir

    def discover_profiles(
        self,
        collection_id: str,
        collection_path: Path
    ) -> List[ProfileManifest]:
        """
        Scan collection for schema v2 profiles.

        Args:
            collection_id: Collection identifier
            collection_path: Path to collection root

        Returns:
            List of valid ProfileManifest objects

        Side Effects:
            Writes manifests to cache_dir/{collection_id}/*.md

        Errors:
            ProfileValidationError if profile structure invalid
        """

    def get_cached_profile(
        self,
        collection_id: str,
        profile_id: str
    ) -> Optional[ProfileManifest]:
        """
        Get profile manifest from cache.

        Args:
            collection_id: Collection identifier
            profile_id: Profile identifier

        Returns:
            ProfileManifest or None if not cached
        """

    def list_cached_profiles(
        self,
        collection_id: Optional[str] = None
    ) -> List[ProfileManifest]:
        """
        List all cached profiles.

        Args:
            collection_id: Optional filter by collection

        Returns:
            List of ProfileManifest objects
        """
```

**Implementation Details**:

```python
def _scan_profiles(self, collection_path: Path) -> List[Path]:
    """
    Find all profile files in collection.

    Args:
        collection_path: Path to collection root

    Returns:
        List of paths to profile .md files

    Scans:
        - {collection_path}/profiles/*.md
        - Recursive scan for nested profiles
    """
    profiles_dir = collection_path / "profiles"
    if not profiles_dir.exists():
        return []

    return list(profiles_dir.glob("**/*.md"))

def _parse_profile_manifest(self, profile_file: Path) -> Optional[ProfileManifest]:
    """
    Parse profile YAML frontmatter.

    Args:
        profile_file: Path to profile .md file

    Returns:
        ProfileManifest or None if invalid

    Format:
        ---
        profile:
          name: myprofile
          schema-version: 2
          version: 1.0.0
        ---

        Profile description...
    """
    import yaml

    content = profile_file.read_text()

    # Extract YAML frontmatter
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    yaml_content = parts[1]

    try:
        data = yaml.safe_load(yaml_content)
        profile_data = data.get("profile", {})

        # Validate schema version
        if profile_data.get("schema-version") != 2:
            logger.warning(
                f"Skipping {profile_file.name}: "
                f"schema-version {profile_data.get('schema-version')} != 2"
            )
            return None

        return ProfileManifest(**profile_data)

    except Exception as e:
        logger.error(f"Failed to parse {profile_file}: {e}")
        return None

def _cache_profile(
    self,
    collection_id: str,
    profile_file: Path,
    manifest: ProfileManifest
) -> None:
    """
    Write profile manifest to cache.

    Args:
        collection_id: Collection identifier
        profile_file: Original profile file path
        manifest: Parsed ProfileManifest

    Side Effects:
        Writes to cache_dir/{collection_id}/{profile_id}.md
    """
    cache_collection_dir = self.cache_dir / collection_id
    cache_collection_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_collection_dir / profile_file.name

    # Copy entire profile file (frontmatter + content)
    shutil.copy2(profile_file, cache_file)

    logger.info(f"Cached profile: {collection_id}/{manifest.name}")
```

**Testing Requirements**:
- Scan collection for profiles
- Parse YAML frontmatter
- Validate schema-version: 2
- Reject schema v1 profiles
- Cache manifests correctly
- Handle invalid YAML
- Handle missing frontmatter
- Concurrent discovery requests

**Dependencies**:
- `pydantic` (data validation)
- `pyyaml` (YAML parsing)
- `pathlib.Path`
- `logging`

---

### Module 4: ProfileCompilationService

**Purpose**: Resolve profile refs and cache compiled assets

**File**: `amplifierd/services/profile_compilation.py`

**Public Contract**:

```python
from pathlib import Path
from typing import Dict

class RefResolutionError(Exception):
    """Raised when ref resolution fails."""
    pass

class ProfileCompilationError(Exception):
    """Raised when profile compilation fails."""
    pass

class ProfileCompilationService:
    """
    Compiles profiles by resolving all refs and caching assets.

    Creates Python module structure for dynamic import.
    """

    def __init__(
        self,
        state_dir: Path,
        fetch_service: CollectionFetchService
    ):
        """
        Initialize with state directory and fetch service.

        Args:
            state_dir: Path to state directory
            fetch_service: CollectionFetchService for resolving refs
        """
        self.state_dir = state_dir
        self.compiled_dir = state_dir / "profiles"
        self.fetch_service = fetch_service

    def compile_profile(
        self,
        collection_id: str,
        profile: ProfileManifest
    ) -> Path:
        """
        Compile profile by resolving all refs.

        Args:
            collection_id: Collection identifier
            profile: ProfileManifest with refs

        Returns:
            Path to state/profiles/{collection}/{uid}/

        Side Effects:
            - Fetches and caches all referenced assets
            - Creates Python module structure

        Errors:
            RefResolutionError if ref invalid
            ProfileCompilationError if compilation fails
        """

    def _resolve_ref(self, ref: str, ref_type: str) -> Path:
        """
        Resolve a reference to local path.

        Args:
            ref: Reference string (git+URL, fsspec path, local path)
            ref_type: Type of ref (agent, context, module, etc.)

        Returns:
            Path to resolved asset

        Errors:
            RefResolutionError if resolution fails
        """

    def _create_module_structure(
        self,
        target_dir: Path,
        assets: Dict[str, List[Path]]
    ) -> None:
        """
        Create Python module structure for compiled profile.

        Args:
            target_dir: Compilation target directory
            assets: Dict mapping asset type to asset paths

        Side Effects:
            Creates __init__.py files and copies assets

        Structure:
            target_dir/
              __init__.py
              orchestrator/
                __init__.py
                module.py
              agents/
                __init__.py
                agent1.md
              context/
                __init__.py
                doc1.md
              ...
        """
```

**Implementation Details**:

```python
def compile_profile(
    self,
    collection_id: str,
    profile: ProfileManifest
) -> Path:
    """Full implementation of profile compilation."""
    import uuid

    # Generate unique ID for this compilation
    profile_uid = str(uuid.uuid4())

    # Create compilation directory
    compile_dir = self.compiled_dir / collection_id / profile_uid
    compile_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Resolve all refs by type
        assets = {
            "orchestrator": [],
            "agents": [],
            "context": [],
            "tools": [],
            "hooks": [],
            "providers": []
        }

        # Resolve agent refs
        for agent_ref in profile.agents or []:
            resolved_path = self._resolve_ref(agent_ref, "agent")
            assets["agents"].append(resolved_path)

        # Resolve context refs
        for context_ref in profile.context or []:
            resolved_path = self._resolve_ref(context_ref, "context")
            assets["context"].append(resolved_path)

        # Resolve module refs (orchestrator, tools, hooks, providers)
        if profile.session and profile.session.orchestrator:
            orch_source = profile.session.orchestrator.source
            resolved_path = self._resolve_ref(orch_source, "orchestrator")
            assets["orchestrator"].append(resolved_path)

        # ... similar for tools, hooks, providers

        # Create module structure
        self._create_module_structure(compile_dir, assets)

        logger.info(f"Compiled profile: {collection_id}/{profile.name} → {profile_uid}")
        return compile_dir

    except Exception as e:
        # Cleanup on failure
        if compile_dir.exists():
            shutil.rmtree(compile_dir)
        raise ProfileCompilationError(f"Compilation failed: {e}")

def _resolve_ref(self, ref: str, ref_type: str) -> Path:
    """Resolve various ref types to local paths."""

    # Handle git+ refs
    if ref.startswith("git+"):
        # Parse: git+https://github.com/org/repo@ref/path/to/asset
        repo_part, asset_path = ref.split("/", 3)[3].split("/", 1)
        collection_path = self.fetch_service.fetch_collection(repo_part)
        return collection_path / asset_path

    # Handle local paths
    elif Path(ref).is_absolute():
        path = Path(ref)
        if not path.exists():
            raise RefResolutionError(f"{ref_type} not found: {ref}")
        return path

    # Handle relative paths
    else:
        # Relative to compilation context (needs context parameter)
        raise RefResolutionError(f"Relative refs not yet supported: {ref}")

def _create_module_structure(
    self,
    target_dir: Path,
    assets: Dict[str, List[Path]]
) -> None:
    """Create Python module structure."""

    # Create root __init__.py
    (target_dir / "__init__.py").write_text(
        '"""Compiled profile module."""\n'
    )

    # Create subdirectory for each asset type
    for asset_type, asset_paths in assets.items():
        if not asset_paths:
            continue

        type_dir = target_dir / asset_type
        type_dir.mkdir(exist_ok=True)

        # Create __init__.py
        (type_dir / "__init__.py").write_text(
            f'"""{asset_type.capitalize()} assets."""\n'
        )

        # Copy assets
        for asset_path in asset_paths:
            if asset_path.is_file():
                shutil.copy2(asset_path, type_dir / asset_path.name)
            elif asset_path.is_dir():
                shutil.copytree(
                    asset_path,
                    type_dir / asset_path.name,
                    dirs_exist_ok=True
                )
```

**Testing Requirements**:
- Resolve git+ refs
- Resolve fsspec refs
- Resolve local refs
- Handle missing refs gracefully
- Create correct module structure
- Verify importability of compiled modules
- Concurrent compilation requests
- Cleanup on failure

**Dependencies**:
- `pathlib.Path`
- `shutil`
- `uuid`
- `logging`
- `CollectionFetchService` (dependency injection)

---

### Module 5: ProfileService (Updated)

**Purpose**: Orchestrate profile operations

**File**: `amplifierd/services/simple_profile_service.py` (update existing)

**Public Contract**:

```python
class ProfileService:
    """
    Orchestrates profile discovery, compilation, and activation.

    High-level service that delegates to specialized services.
    """

    def __init__(
        self,
        discovery: ProfileDiscoveryService,
        compilation: ProfileCompilationService,
        sources: CollectionSourcesService,
        fetch: CollectionFetchService,
        active_profile_file: Path
    ):
        """
        Initialize with all required services.

        Args:
            discovery: ProfileDiscoveryService
            compilation: ProfileCompilationService
            sources: CollectionSourcesService
            fetch: CollectionFetchService
            active_profile_file: Path to active_profile.txt
        """

    def list_profiles(self) -> List[ProfileManifest]:
        """
        List all discovered profiles.

        Returns:
            List of ProfileManifest objects from all collections

        Note: Reads from cache, doesn't re-scan
        """

    def get_profile(
        self,
        collection_id: str,
        profile_id: str
    ) -> ProfileManifest:
        """
        Get specific profile manifest.

        Args:
            collection_id: Collection identifier
            profile_id: Profile identifier

        Returns:
            ProfileManifest

        Errors:
            ProfileNotFoundError if profile doesn't exist
        """

    def sync_collections(self) -> Dict[str, int]:
        """
        Sync all collections and discover profiles.

        Returns:
            Dict mapping collection_id to profile_count

        Side Effects:
            - Fetches all collections
            - Discovers profiles
            - Updates cache
        """

    def compile_and_activate(
        self,
        collection_id: str,
        profile_id: str
    ) -> Path:
        """
        Compile profile and set as active.

        Args:
            collection_id: Collection identifier
            profile_id: Profile identifier

        Returns:
            Path to compiled profile directory

        Side Effects:
            - Compiles profile (resolves refs, caches assets)
            - Updates active_profile.txt

        Errors:
            ProfileNotFoundError if profile doesn't exist
            ProfileCompilationError if compilation fails
        """
```

**Implementation Notes**:

- Service acts as orchestrator only
- Delegates to specialized services
- No business logic in this layer
- Simple error propagation

---

## Data Migration Strategy

### Migration Script

**File**: `amplifierd/migration/collections_v2.py`

**Purpose**: Migrate from collections.yaml to collection-sources.txt

**Execution**: Run automatically on daemon startup if old format detected

**Steps**:

1. **Detect Migration Need**
   ```python
   def needs_migration(share_dir: Path) -> bool:
       """Check if migration needed."""
       yaml_file = share_dir / "collections.yaml"
       txt_file = share_dir / "collection-sources.txt"

       # Need migration if YAML exists but text doesn't
       return yaml_file.exists() and not txt_file.exists()
   ```

2. **Backup Old Files**
   ```python
   def backup_old_registry(share_dir: Path) -> Path:
       """Backup collections.yaml before migration."""
       yaml_file = share_dir / "collections.yaml"
       backup_file = yaml_file.with_suffix('.yaml.backup')
       shutil.copy2(yaml_file, backup_file)
       return backup_file
   ```

3. **Convert Registry Format**
   ```python
   def convert_registry(yaml_file: Path, txt_file: Path) -> None:
       """Convert YAML registry to text format."""
       import yaml

       registry = yaml.safe_load(yaml_file.read_text())

       with txt_file.open('w') as f:
           f.write("# Collections registry (migrated from collections.yaml)\n")
           f.write("# Format: <collection-id> <source-ref>\n\n")

           for collection in registry.get('collections', []):
               coll_id = collection.get('id')
               source = collection.get('source')
               f.write(f"{coll_id} {source}\n")
   ```

4. **Migrate Profile Cache**
   ```python
   def migrate_profile_cache(share_dir: Path) -> None:
       """Reorganize profiles into collection-scoped directories."""
       old_profiles = share_dir / "profiles"

       # If profiles are already organized by collection, nothing to do
       # If flat, need to extract collection from frontmatter

       for profile_file in old_profiles.rglob("*.md"):
           # Parse frontmatter to get collection
           manifest = parse_profile_frontmatter(profile_file)
           collection_id = manifest.get('collection', 'unknown')

           # Create collection directory
           new_dir = old_profiles / collection_id
           new_dir.mkdir(exist_ok=True)

           # Move profile
           new_path = new_dir / profile_file.name
           if new_path != profile_file:
               shutil.move(profile_file, new_path)
   ```

5. **Validate Schema Versions**
   ```python
   def validate_and_deprecate(share_dir: Path) -> Dict[str, int]:
       """Validate profiles, deprecate schema v1."""
       profiles_dir = share_dir / "profiles"

       stats = {"valid": 0, "deprecated": 0, "invalid": 0}

       for profile_file in profiles_dir.rglob("*.md"):
           manifest = parse_profile_frontmatter(profile_file)
           schema_version = manifest.get('schema-version')

           if schema_version == 2:
               stats["valid"] += 1
           elif schema_version == 1:
               # Rename to .deprecated
               profile_file.rename(
                   profile_file.with_suffix('.md.deprecated')
               )
               stats["deprecated"] += 1
           else:
               stats["invalid"] += 1

       return stats
   ```

6. **Report Migration**
   ```python
   def report_migration(
       backup_path: Path,
       stats: Dict[str, int]
   ) -> None:
       """Log migration results."""
       logger.info("=" * 60)
       logger.info("Collections Migration Complete")
       logger.info("=" * 60)
       logger.info(f"Backup saved: {backup_path}")
       logger.info(f"Valid profiles (v2): {stats['valid']}")
       logger.info(f"Deprecated profiles (v1): {stats['deprecated']}")
       logger.info(f"Invalid profiles: {stats['invalid']}")
       logger.info("")
       logger.info("Schema v1 profiles have been deprecated.")
       logger.info("Please update to schema v2 or use conversion tool.")
       logger.info("=" * 60)
   ```

### Migration Integration

**In `amplifierd/main.py` startup**:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with migration."""
    logger.info("Starting amplifierd daemon")

    # Check for migration
    if migration.needs_migration(config.share_dir):
        logger.info("Detected old registry format, migrating...")

        try:
            migration.run_migration(config.share_dir)
            logger.info("Migration successful")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            logger.error("Please check backup and contact support")
            raise

    # Continue with normal startup
    collection_service = get_collection_service()
    await collection_service.sync_collections()

    yield

    logger.info("Shutting down amplifierd daemon")
```

### Rollback Strategy

If migration fails or issues found:

1. **Restore from backup**:
   ```bash
   cd $AMPLIFIERD_ROOT/local/share
   mv collections.yaml.backup collections.yaml
   rm collection-sources.txt
   ```

2. **Downgrade daemon version**:
   ```bash
   pip install amplifierd==<previous-version>
   ```

3. **Report issue**: Include backup files and error logs

---

## Testing Strategy

### Unit Tests

**Per Module**:

1. **CollectionSourcesService**
   - Parse valid lines
   - Skip comments/empty lines
   - Reject invalid IDs
   - Add source (duplicate check)
   - Remove source (not found check)
   - Atomic writes

2. **CollectionFetchService**
   - Git clone (mocked)
   - Git commit caching
   - Fsspec local resolution
   - Fsspec remote caching
   - Bundled collection resolution
   - Error handling

3. **ProfileDiscoveryService**
   - Scan collection directories
   - Parse YAML frontmatter
   - Validate schema v2
   - Reject schema v1
   - Cache manifests
   - Handle parse errors

4. **ProfileCompilationService**
   - Resolve git refs
   - Resolve fsspec refs
   - Resolve local refs
   - Create module structure
   - Handle resolution errors
   - Verify importability

5. **Migration Script**
   - Detect migration need
   - Convert YAML to text
   - Migrate profile cache
   - Validate schema versions
   - Backup creation

### Integration Tests

**End-to-End Flows**:

1. **Add Collection Flow**
   - POST /api/v1/collections/
   - Verify collection-sources.txt updated
   - Verify collection fetched
   - Verify profiles discovered
   - Verify profiles cached

2. **Activate Profile Flow**
   - POST /api/v1/profiles/{collection}/{profile}/activate
   - Verify profile compiled
   - Verify assets cached
   - Verify active_profile.txt updated

3. **Sync Collections Flow**
   - POST /api/v1/collections/sync
   - Verify all collections updated
   - Verify new profiles discovered
   - Verify cache updated

4. **Migration Flow**
   - Start daemon with old format
   - Verify migration triggered
   - Verify backup created
   - Verify new format working
   - Verify profiles validated

### Performance Tests

**Benchmarks**:

1. **Git Clone Performance**
   - Measure clone time for various repo sizes
   - Verify shallow clone optimization
   - Test concurrent clones

2. **Profile Discovery Performance**
   - Measure scan time for various collection sizes
   - Test concurrent discoveries
   - Verify caching effectiveness

3. **Compilation Performance**
   - Measure compilation time for various profile sizes
   - Test concurrent compilations
   - Verify asset caching effectiveness

### Test Data

**Sample Collections**:

1. **Small Collection**
   - 3 profiles
   - 5 agents
   - Minimal refs

2. **Medium Collection**
   - 10 profiles
   - 20 agents
   - Mix of git and local refs

3. **Large Collection**
   - 50 profiles
   - 100 agents
   - Complex ref chains

**Schema Versions**:

1. Schema v1 profiles (for migration testing)
2. Schema v2 profiles (valid)
3. Invalid profiles (malformed YAML)

---

## Rollout Plan

### Phase 1: Internal Testing (Week 4)

**Goal**: Validate implementation with test data

**Activities**:
1. Deploy to test VM
2. Run migration on sample data
3. Test all API endpoints
4. Validate profiles compile correctly
5. Performance benchmarks

**Criteria**:
- All tests pass
- Migration successful on test data
- Performance acceptable
- No critical bugs

### Phase 2: Alpha Release (Week 5)

**Goal**: Deploy to select alpha users

**Activities**:
1. Release notes prepared
2. Migration guide published
3. Deploy to alpha users
4. Monitor for issues
5. Gather feedback

**Criteria**:
- No data loss
- Migration smooth
- No blocking issues
- Positive feedback

### Phase 3: Beta Release (Week 6)

**Goal**: Wider deployment

**Activities**:
1. Address alpha feedback
2. Update documentation
3. Deploy to beta users
4. Continue monitoring

**Criteria**:
- All alpha issues resolved
- Documentation complete
- Beta users onboarded
- Stability confirmed

### Phase 4: General Release (Week 7)

**Goal**: Full production deployment

**Activities**:
1. Final testing
2. Release announcement
3. Deploy to all users
4. Support channels active

**Criteria**:
- Zero critical bugs
- Migration process smooth
- Documentation comprehensive
- Support ready

---

## Risk Mitigation

### Risk 1: Data Loss During Migration

**Likelihood**: Medium
**Impact**: High

**Mitigation**:
- Automatic backups before migration
- Migration validation step
- Rollback procedure documented
- Test on sample data first

**Contingency**:
- Restore from backup
- Downgrade daemon version
- Manual data recovery if needed

---

### Risk 2: Git Clone Failures

**Likelihood**: Medium
**Impact**: Medium

**Mitigation**:
- Retry logic with exponential backoff
- Timeout configuration
- Clear error messages
- Offline mode (use cached data)

**Contingency**:
- Manual git operations
- Local collection workaround
- Support ticket system

---

### Risk 3: Schema v1 Profile Breakage

**Likelihood**: High
**Impact**: High

**Mitigation**:
- Clear deprecation warnings
- Conversion tool provided
- Migration guide with examples
- Bundled collections updated to v2

**Contingency**:
- Keep v1 support for one more release
- Provide manual conversion service
- Extended support period

---

### Risk 4: Performance Degradation

**Likelihood**: Low
**Impact**: Medium

**Mitigation**:
- Performance testing pre-release
- Caching strategies
- Background sync operations
- Monitoring and profiling

**Contingency**:
- Optimization pass
- Caching improvements
- Resource limits configuration

---

### Risk 5: Ref Resolution Complexity

**Likelihood**: Medium
**Impact**: Medium

**Mitigation**:
- Start with simple refs (git, local)
- Add fsspec gradually
- Clear error messages
- Example profiles

**Contingency**:
- Simplify ref syntax
- Limit supported ref types
- Better documentation

---

## Appendices

### Appendix A: File Changes Summary

**New Files**:
- `amplifierd/services/collection_sources.py`
- `amplifierd/services/collection_fetch.py`
- `amplifierd/services/profile_discovery.py`
- `amplifierd/services/profile_compilation.py`
- `amplifierd/migration/collections_v2.py`
- `tests/services/test_collection_sources.py`
- `tests/services/test_collection_fetch.py`
- `tests/services/test_profile_discovery.py`
- `tests/services/test_profile_compilation.py`
- `tests/migration/test_migration.py`
- `docs/migration_guide.md`

**Modified Files**:
- `amplifierd/models/collections.py` (add schema_version, remove extends)
- `amplifierd/models/profiles.py` (add compilation fields)
- `amplifierd/services/simple_profile_service.py` (update to use new services)
- `amplifierd/routers/collections.py` (update endpoints)
- `amplifierd/routers/profiles.py` (add compilation endpoints)
- `amplifierd/core/config.py` (add new paths)
- `amplifierd/main.py` (add migration check)
- `README.md` (update documentation)

**Removed Files**:
- `amplifierd/services/collection_registry.py` (replaced by collection_sources)

---

### Appendix B: Configuration Changes

**New Paths in config**:

```python
class Config:
    # Existing
    data_dir: Path
    share_dir: Path
    state_dir: Path

    # New
    @property
    def collection_sources_file(self) -> Path:
        """Path to collection-sources.txt."""
        return self.share_dir / "collection-sources.txt"

    @property
    def git_cache_dir(self) -> Path:
        """Path to git checkout cache."""
        return self.state_dir / "git"

    @property
    def profile_cache_dir(self) -> Path:
        """Path to profile manifest cache."""
        return self.share_dir / "profiles"

    @property
    def compiled_profiles_dir(self) -> Path:
        """Path to compiled profiles."""
        return self.state_dir / "profiles"
```

---

### Appendix C: API Changes

**Collection Endpoints**:

| Endpoint | Old Response | New Response | Breaking? |
|----------|--------------|--------------|-----------|
| GET /api/v1/collections/ | List with metadata | Simplified list | Yes |
| GET /api/v1/collections/{id} | Full details | Simplified details | Yes |
| POST /api/v1/collections/ | Same | Add profiles_count | No |
| DELETE /api/v1/collections/{id} | Same | Same | No |
| POST /api/v1/collections/sync | Same | Add per-collection stats | No |

**Profile Endpoints**:

| Endpoint | Old Response | New Response | Breaking? |
|----------|--------------|--------------|-----------|
| GET /api/v1/profiles/ | List all | Collection-scoped list | Partial |
| GET /api/v1/profiles/{name} | Profile details | Add compilation status | No |
| POST /api/v1/profiles/{name}/activate | Activate | Add compilation endpoint | No |
| POST /api/v1/profiles/{name}/compile | N/A | New endpoint | No |

---

### Appendix D: CLI Changes

**Command**: `amplifier collection add`

Old:
```bash
amplifier collection add myrepo git+https://github.com/org/repo
```

New (same):
```bash
amplifier collection add myrepo git+https://github.com/org/repo@main
```

**Command**: `amplifier profile activate`

Old:
```bash
amplifier profile activate myprofile
```

New:
```bash
amplifier profile activate myrepo/myprofile
```

**Command**: `amplifier collection list`

Old output:
```
foundation (v1.0.0) - 3 profiles, 5 agents
  installed: 2025-01-15
```

New output:
```
foundation - bundled:amplifierd.data.collections.foundation
  3 profiles discovered
```

---

### Appendix E: Error Messages

**Schema Version Mismatch**:
```
Error: Profile 'myprofile' has schema-version 1, but daemon requires schema-version 2.

Please update your profile to schema v2 or use the conversion tool:
  amplifier profile convert myprofile

See migration guide: https://docs.amplifier.dev/migration/schema-v2
```

**Collection Fetch Failure**:
```
Error: Failed to fetch collection 'myrepo'
  Source: git+https://github.com/org/repo@main
  Reason: Repository not found or network error

Troubleshooting:
  1. Check repository URL is correct
  2. Verify network connectivity
  3. Check authentication (if private repo)
  4. Try manual git clone: git clone https://github.com/org/repo
```

**Ref Resolution Failure**:
```
Error: Failed to compile profile 'myprofile'
  Agent ref cannot be resolved: git+https://github.com/org/repo@main/agents/missing.md

Troubleshooting:
  1. Verify agent file exists in repository
  2. Check git ref is correct (branch/tag/commit)
  3. Try manual checkout: git clone https://github.com/org/repo
```

---

### Appendix F: Testing Checklist

**Pre-Release**:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Migration tested on sample data
- [ ] Performance benchmarks meet targets
- [ ] API documentation updated
- [ ] CLI help updated
- [ ] Migration guide written
- [ ] Rollback procedure tested
- [ ] Alpha users identified
- [ ] Support channels ready

**Post-Release**:
- [ ] Monitor for errors
- [ ] Gather feedback
- [ ] Track performance metrics
- [ ] Update documentation based on feedback
- [ ] Address reported issues
- [ ] Plan next iteration

---

## Conclusion

This implementation plan provides a comprehensive roadmap for redesigning the amplifierd collections and profiles system. The plan follows the principles of ruthless simplicity and modular design, with clear service boundaries, explicit data flows, and thorough testing.

**Key Takeaways**:

1. **Simplification**: Text file registry vs YAML, direct paths vs extraction
2. **Explicit**: Schema versioning, compilation step, clear boundaries
3. **Testable**: Unit tests, integration tests, migration tests
4. **Mitigated**: Risks identified with contingencies
5. **Rollout**: Phased approach with validation gates

**Next Steps**:

1. Review this plan with team
2. Create implementation tickets
3. Begin Phase 1: Foundation
4. Track progress against timeline
5. Adjust plan based on learnings

**Questions/Clarifications**:

- Confirm bundled collection format still valid?
- Clarify profile UID generation (UUID vs hash?)
- Define "compiled profile" import contract?
- Review ref resolution syntax?

---

**Document Status**: Ready for Review
**Last Updated**: 2025-11-24
**Next Review**: After Phase 1 completion
