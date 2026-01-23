# Bundles

Bundles are the primary mechanism for configuring agent behavior in Amplifier. A bundle defines what tools, context, and capabilities an agent has access to during a session.

## Overview

Bundles replace the previous "profile" system with a simpler, more modular approach based on the Amplifier Foundation library. Instead of a complex multi-stage compilation pipeline, bundles are loaded directly and converted to mount plans.

## Bundle Structure

A bundle is a directory containing configuration files:

```
my-bundle/
├── bundle.yaml          # Main configuration file
├── agents/              # Agent definition files
│   └── main-agent.md
├── context/             # Context files
│   └── project-context.md
└── tools/               # Tool configurations
    └── filesystem.yaml
```

## bundle.yaml

The main configuration file defines the bundle metadata and module references:

```yaml
bundle:
  name: my-bundle
  version: 1.0.0
  description: A custom agent configuration

modules:
  orchestrator: orchestrator/sequential
  context_manager: context/simple

  agents:
    - ./agents/main-agent.md

  tools:
    - tool-filesystem
    - tool-bash

  context:
    - ./context/project-context.md
```

## Bundle Locations

Bundles can be loaded from:

1. **Well-known paths**: `~/.amplifierd/bundles/{bundle-name}/`
2. **Relative paths**: `./bundles/my-bundle/`
3. **Absolute paths**: `/path/to/my-bundle/`

## Using Bundles

### Creating a Session with a Bundle

```python
from amplifier_library.bundles import LakehouseBundleManager

manager = LakehouseBundleManager()
mount_plan = await manager.generate_mount_plan(
    bundle_ref="foundation/base",
    session_id="sess_123",
    amplified_dir="/path/to/project",
)
```

### Via the API

```bash
curl -X POST http://localhost:8420/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"bundle_name": "foundation/base", "amplified_dir": "."}'
```

## Migration from Profiles

The bundle system replaces the previous profile system. Key changes:

| Old (Profiles) | New (Bundles) |
|----------------|---------------|
| `profile_name` | `bundle_name` |
| `MountPlanService` | `LakehouseBundleManager` |
| 8-stage compilation | Direct loading |
| `~/.amplifierd/profiles/` | `~/.amplifierd/bundles/` |

## LakehouseBundleManager

The `LakehouseBundleManager` class provides the main interface for working with bundles:

```python
from amplifier_library.bundles import LakehouseBundleManager

manager = LakehouseBundleManager()

# Generate a mount plan for a session
mount_plan = await manager.generate_mount_plan(
    bundle_ref="foundation/base",
    session_id="preview_123",
    amplified_dir="/data/projects/my-project",
    api_key="sk-...",  # Optional API key injection
)
```

### Key Methods

- `generate_mount_plan(bundle_ref, session_id, amplified_dir, api_key)` - Load bundle and generate mount plan with runtime configuration injected

## Runtime Configuration Injection

When generating a mount plan, the following runtime configuration is automatically injected:

- **working_dir**: Set to the amplified directory for relative path resolution
- **allowed_write_paths**: Restricts file writes to the amplified directory
- **session_log_template**: Configures logging paths
- **api_key**: Injected into provider configurations

## Foundation Integration

Bundles are built on the Amplifier Foundation library which provides:

- Bundle loading and validation
- Module resolution and composition
- Registry integration for shared modules

See the [Amplifier Foundation documentation](https://github.com/microsoft/amplifier-foundation) for more details.
