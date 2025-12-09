# V3 Profile Compiler

Compiler for v3 profile format that generates mount plans for the Amplifier system.

## Quick Start

```bash
python compile_profile.py software-developer.yaml config.yaml SOURCES.txt output.json
```

## Compilation Process

**Input:** v3 profile YAML, SOURCES.txt, and config.yaml

**Steps:**
1. **Load Behavior Definitions** - Recursively loads all behaviors and their dependencies
2. **Gather Component IDs:**
   - Collect orchestrator, context, providers, contexts from profile
   - Topologically sort behaviors by their `requires` dependencies
   - For each behavior, gather hooks, agents, contexts, tools
3. **Cache Assets:**
   - Validate all component IDs exist in SOURCES.txt
   - Resolve and download assets from sources (git repos, URLs, local paths)
   - Cache assets to avoid repeated downloads
4. **Generate Mount Plan:**
   - Merge configs: root config.yaml → behavior-specific overrides (in dependency order)
   - Non-namespaced session config values go into `settings` key
   - Expand agents with content from asset files
   - Add `working_dir` param to all tools from `session.working_dir` config

**Output:** Mount plan JSON (compatible with Amplifier runtime)

## Development Workflow

### Working on Specific Components

To work on a specific behavior, tool, provider, orchestrator, hook, context, or agent:
- Update its source reference in SOURCES.txt to point to your dev version
- Example: `tool.tool-bash file:///home/user/dev/tool-bash`

### Using Different Component Versions

To use a different version of a component in a specific behavior:
- Reference the new version in SOURCES.txt
- The compiler will download and use that version instead

## Files

- `compile_profile.py` - The compiler script (uses amplifierd's RefResolutionService)
- `software-developer.yaml` - Example v3 profile
- `config.yaml` - Configuration with session, provider, and hook settings
- `SOURCES.txt` - Component ID to source mappings
- `software-developer_mount_plan.json` - Example output format

## Features

- ✓ Recursive dependency loading for behaviors
- ✓ Topological sorting of behavior dependencies
- ✓ Asset caching (git repos, HTTP URLs, local paths)
- ✓ Config merging with behavior-specific overrides
- ✓ Clear error messages for missing/circular dependencies
- ✓ Automatic `working_dir` injection for tools
- ✓ Agent content expansion from source files
