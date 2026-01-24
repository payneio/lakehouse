Implement the following plan:

# Plan: Align Bundle Architecture with Foundation

## Code Review Findings

### Current Flow (Broken)

1. **Daemon startup** (`main.py:90-91`):

- Calls `handle_startup_updates(daemon_config.startup)`

2. **handle_startup_updates** (`startup/__init__.py:26`):

- Calls `_sync_system_bundles()`

3. **\_sync_system_bundles** (`startup/__init__.py:51`):

- Calls `sync_bundles_from_file(bundles_file, bundles_dir)`
- **Downloads individual files** from GitHub raw URLs to `~/.lakehoused/share/bundles/`

4. **Session creation** (`sessions.py:300`):

- Creates `LakehouseBundleManager()` **fresh with no args**
- Manager discovers synced files and registers with `file://` URIs

5. **Bundle loading** (`manager.py:191`):

- Calls `self._registry.load(bundle_ref)`
- Foundation can't resolve `namespace:path` because only single file exists

### Root Cause

`LakehouseBundleManager()` is created fresh in each endpoint without receiving the git+ URIs from BUNDLES.txt. The startup sync downloads files to disk, and the manager
discovers them as `file://` URIs.

## Problem Summary

The current architecture downloads individual bundle files via HTTP and registers them with `file://` URIs. This breaks `namespace:path` resolution because:

1. `foundation.md` synced to `~/.lakehoused/share/bundles/foundation.md`
2. Registered as `file://...foundation.md`
3. Bundle includes `foundation:behaviors/sessions`
4. Foundation looks for `~/.lakehoused/share/bundles/behaviors/sessions`
5. **Fails** - only the single file was synced, not the `behaviors/` directory

## Correct Architecture (Aligned with CLI)

The CLI does this:

```python
# Register well-known bundles (hardcoded dict)
for name, info in WELL_KNOWN_BUNDLES.items():
self._registry.register({name: info["remote"]})

# Load a bundle - Foundation handles everything
bundle = await registry.load("amplifier-dev")
```

We should do the same:

```python
# Parse BUNDLES.txt and register with Foundation
for name, uri in parse_bundles_txt().items():
registry.register({name: uri})

# Load a bundle - Foundation handles everything
bundle = await registry.load("foundation")
```

### BUNDLES.txt = Name Registry (not file sync)

```txt
# BUNDLES.txt is a registry mapping bundle names to git+ URIs
# Foundation handles cloning/caching full repos to ~/.amplifier/cache/
foundation:git+https://github.com/microsoft/amplifier-foundation@main
amplifier-dev:git+https://github.com/microsoft/amplifier-foundation@main#bundles/amplifier-dev.yaml
software-developer:git+https://github.com/payneio/payne-amplifier@main#bundles/software-developer.md
```

### Bundle Discovery Flow

```
┌─────────────────────────────────────────────────────────────┐
│ BUNDLES.txt (registry)                                       │
│ name → git+ URI                                              │
└────────────────────────────┬────────────────────────────────┘
│ (NO file download)
▼
┌─────────────────────────────────────────────────────────────┐
│ LakehouseBundleManager.register()                           │
│ Register git+ URIs directly with Foundation                  │
└────────────────────────────┬────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Session Creation: await load_bundle("foundation")            │
│ Foundation clones repo to ~/.amplifier/cache/                │
│ Full repo structure available for namespace:path resolution  │
└─────────────────────────────────────────────────────────────┘
```

### Local Bundles = Directories

```
~/.lakehoused/share/bundles/
├── BUNDLES.txt                 # Registry (name→git+ URI)
├── my-custom-bundle/           # Directory, not file!
│   ├── bundle.md               # Main bundle file
│   ├── behaviors/
│   │   └── my-behavior.yaml
│   └── agents/
│       └── my-agent.yaml
└── another-local-bundle/
└── bundle.yaml
```

## Implementation Steps

### Step 1: Simplify bundle_sync.py to parse-only

**File**: `lakehoused/lakehoused/startup/bundle_sync.py`

Remove file download logic. Just parse BUNDLES.txt and return mappings:

```python
def parse_bundles_file(bundles_txt_path: Path) -> dict[str, str]:
"""Parse BUNDLES.txt and return name→URI mappings.

Does NOT download files. The URIs are registered directly with
Foundation's BundleRegistry, which handles git cloning/caching.
"""
if not bundles_txt_path.exists():
bundles_txt_path.parent.mkdir(parents=True, exist_ok=True)
bundles_txt_path.write_text(DEFAULT_BUNDLES_TXT)

bundles = {}
for line in bundles_txt_path.read_text().strip().split("\n"):
line = line.strip()
if not line or line.startswith("#"):
continue
if ":" not in line:
continue
name, uri = line.split(":", 1)
bundles[name.strip()] = uri.strip()

return bundles
```

Update `DEFAULT_BUNDLES_TXT` with git+ URIs (no raw file URLs).

**Delete**: `sync_bundle()`, `sync_bundles_from_file()`, `fetch_url_content()`, `to_raw_github_url()` - all file download logic.

### Step 2: Update LakehouseBundleManager

**File**: `lakehouse_library/bundles/manager.py`

1. **Add `registry_bundles` parameter to `__init__`**:

```python
def __init__(
self,
home_dir: Path | None = None,
registry_bundles: dict[str, str] | None = None,  # NEW
) -> None:
self._home_dir = home_dir or get_home_dir()
self._bundles_dir = self._home_dir / "bundles"
self._share_bundles_dir = self._home_dir / "share" / "bundles"
self._registry = BundleRegistry(home=self._home_dir)
self._bundle_info: dict[str, BundleInfo] = {}

# Register bundles from BUNDLES.txt (git+ URIs) FIRST
if registry_bundles:
self._registry.register(registry_bundles)
logger.info(f"Registered {len(registry_bundles)} bundles from BUNDLES.txt")

# Then discover local bundles (directories only)
self._discover_local_bundles()
```

2. **Update `_discover_bundles_in_dir()` to skip single files**:

- Only register directories containing `bundle.md`/`bundle.yaml`
- Skip individual `.md`/`.yaml` files (these are synced artifacts)

### Step 3: Update daemon startup to pass registry bundles

**File**: `lakehoused/lakehoused/startup/__init__.py`

```python
async def _sync_system_bundles() -> None:
"""Parse BUNDLES.txt and register bundles for use in sessions."""
from lakehouse_library.storage.paths import get_bundles_dir
from .bundle_sync import parse_bundles_file

bundles_dir = get_bundles_dir()
bundles_file = bundles_dir / "BUNDLES.txt"

# Parse BUNDLES.txt (creates default if missing)
registry_bundles = parse_bundles_file(bundles_file)

# Store for use by LakehouseBundleManager instances
_REGISTRY_BUNDLES.update(registry_bundles)

logger.info(f"Parsed {len(registry_bundles)} bundles from BUNDLES.txt")

# Module-level cache for parsed bundles
_REGISTRY_BUNDLES: dict[str, str] = {}

def get_registry_bundles() -> dict[str, str]:
"""Get parsed bundles from BUNDLES.txt."""
return _REGISTRY_BUNDLES.copy()
```

### Step 4: Update session endpoints to pass registry bundles

**File**: `lakehoused/lakehoused/routers/sessions.py`

Update `create_session()` and `change_session_bundle()`:

```python
from ..startup import get_registry_bundles

# In create_session():
bundle_manager = LakehouseBundleManager(
registry_bundles=get_registry_bundles(),
)
```

### Step 5: Clean up stale files

```bash
# Remove synced single-file bundles (broken approach)
rm ~/.lakehoused/share/bundles/*.md
rm ~/.lakehoused/share/bundles/*.yaml
# Keep BUNDLES.txt
```

Update user's BUNDLES.txt to use git+ URIs instead of relying on synced files.

## Files to Modify

| File                                           | Change                                                            |
| ---------------------------------------------- | ----------------------------------------------------------------- |
| `lakehoused/lakehoused/startup/bundle_sync.py` | Replace with simple `parse_bundles_file()`, delete download logic |
| `lakehouse_library/bundles/manager.py`         | Add `registry_bundles` param, skip single files in discovery      |
| `lakehoused/lakehoused/startup/__init__.py`    | Add `_REGISTRY_BUNDLES` cache and `get_registry_bundles()`        |
| `lakehoused/lakehoused/routers/sessions.py`    | Pass `registry_bundles` to LakehouseBundleManager (2 locations)   |
| `lakehoused/lakehoused/routers/bundles.py`     | Pass `registry_bundles` to LakehouseBundleManager                 |
| Tests for above files                          | Update mocks/fixtures for new function signatures                 |

## Directory Structure Changes

**Before** (broken):

```
~/.lakehoused/
├── share/bundles/
│   ├── BUNDLES.txt
│   ├── foundation.md        # Single file - BROKEN!
│   ├── amplifier-dev.yaml   # Single file - BROKEN!
│   └── software-developer.md
```

**After** (correct):

```
~/.lakehoused/
├── share/bundles/
│   ├── BUNDLES.txt          # Registry (name→git+ URI)
│   └── my-custom-bundle/    # Local bundles are directories
│       ├── bundle.md
│       └── behaviors/
│           └── my-behavior.yaml
~/.amplifier/cache/           # Foundation's git clone cache
├── amplifier-foundation-xxx/
│   ├── bundle.md
│   ├── behaviors/
│   │   ├── sessions.yaml
│   │   ├── logging.yaml
│   │   └── ...
│   └── bundles/
│       ├── amplifier-dev.yaml
│       └── minimal.yaml
```

## Verification

### Unit Tests

```bash
cd lakehoused && uv run pytest tests/ -v
cd lakehouse_library && uv run pytest tests/ -v
```

### Integration Test

```bash
# 1. Clean up stale files
rm ~/.lakehoused/share/bundles/*.md ~/.lakehoused/share/bundles/*.yaml 2>/dev/null || true

# 2. Restart daemon
make daemon-dev  # or: cd lakehoused && uv run python -m lakehoused

# 3. Check startup logs for:
#    - "Parsed N bundles from BUNDLES.txt"
#    - NO "Include could not be resolved" warnings

# 4. Create test session via API or webapp
curl -X POST http://localhost:8420/api/v1/sessions/ \
-H "Content-Type: application/json" \
-d '{"project_path": ".", "bundle_name": "foundation"}'

# 5. Check mount_plan.json for session - should have:
#    - hooks from foundation:behaviors/sessions (hook-logging)
#    - tools from foundation (tool-filesystem, etc.)

# 6. Check ~/.amplifier/cache/ for cloned repos (Foundation's cache)
ls ~/.amplifier/cache/
```

### Test Local Bundle (directories work)

```bash
# Create test bundle directory
mkdir -p ~/.lakehoused/share/bundles/test-local/
cat > ~/.lakehoused/share/bundles/test-local/bundle.yaml << 'EOF'
bundle:
name: test-local
version: 1.0.0
description: Test local directory bundle
EOF

# Restart daemon and verify it's discovered
# Should see: "Registered local bundle: test-local"
```

## Key Insights

### Bundles are Directories

The fundamental issue was treating bundles as single files when they are inherently directories/repos. This plan aligns the architecture with that reality:

- **BUNDLES.txt** = registry of names to git+ URIs (not file sync)
- **Foundation** = handles git cloning/caching (preserves repo structure)
- **Local bundles** = directories (can have behaviors/, modules/, etc.)
- **`namespace:path`** = works because full repo structure is available

### Sub-Bundles are Handled Implicitly

The `sub_bundles` metadata in `bundle.md` (e.g., `amplifier-dev`, `minimal`) is **declarative documentation**, not runtime configuration. Foundation already handles sub-bundle
detection implicitly:

1. When Foundation loads `foundation:behaviors/sessions`:

- Clones the `foundation` repo (if not cached)
- Resolves `behaviors/sessions.yaml` within the repo
- Walks up directory tree to find root bundle
- Marks it with `is_root: False` and `root_name: "foundation"`
- Persists to `~/.amplifier/registry.json`

2. The CLI reads `registry.json` to categorize bundles:

```python
if not bundle_data.get("is_root", True):
# Sub-bundle (behavior, provider, etc.)
categories["sub_bundles"].append(entry)
```

3. The `sub_bundles` metadata in `bundle.md` is for:

- Documentation (what sub-bundles are available)
- CLI discoverability (`amplifier bundle list`)
- NOT for runtime bundle loading

**Implication**: We don't need to implement `sub_bundles` processing. We just need to register bundles with proper `git+` URIs and Foundation handles the rest.

If you need specific details from before exiting plan mode (like exact code snippets, error messages, or content you generated), read the full transcript at:
/home/payne/.claude/projects/-data-repos-lakehouse/51e7980b-50a9-43bc-b6d8-d83c4eb0376b.jsonl
