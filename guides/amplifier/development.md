# Amplifier Development Guide

## Introduction

This guide covers development workflows for working with Amplifier itself and creating custom modules and collections. Whether you're contributing to Amplifier core or building your own extensions, this guide provides the practical workflows and best practices you need.

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Dependency Management with uv](#dependency-management-with-uv)
3. [Git Workflow and Submodules](#git-workflow-and-submodules)
4. [Custom Module Development](#custom-module-development)
5. [Custom Collection Development](#custom-collection-development)
6. [Local Testing](#local-testing)
7. [Packaging and Distribution](#packaging-and-distribution)
8. [Debugging](#debugging)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Development Environment Setup

### Prerequisites

**Install uv** (Python package manager):

```bash
# macOS/Linux/WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation**:

```bash
uv --version
# Should show: uv 0.x.x
```

### Clone amplifier-dev Repository

- The `amplifier-dev` repo contains a shell repo that links amplifier-core, amplifier-app-cli, and amplifier-module-resolution together for development.
- We work on Amplifier in `amplifier` v1, generally on Brian's `brkrabac/amplifier-v2-codespace` branch.
- Locally: `/data/repos/msft/amplifier`

```bash
git clone --recursive https://github.com/microsoft/amplifier@brkrabac/amplifier-v2-codespace
cd amplifier

# If already cloned without --recursive:
git submodule update --init --recursive
```

To just get the amplifier-dev repo without Brian's codespace:

```bash
# Clone with submodules
git clone --recursive https://github.com/microsoft/amplifier-dev
cd amplifier-dev
```

### Run Development Installation Script

Amplifier provides installation scripts that:
1. Install all core packages in editable mode
2. Install all modules in editable mode
3. Configure local source mappings
4. Set up development profiles

**On macOS/Linux/WSL**:

```bash
./scripts/install-dev.sh
```

**On Windows**:

```powershell
.\scripts\install-dev.ps1
```

**What this does**:

```bash
# For each submodule:
cd amplifier-core
uv pip install -e .

cd ../amplifier-app-cli
uv pip install -e .

# For each module:
cd ../amplifier-module-provider-anthropic
uv pip install -e .

# And so on...
```

After running the install script, the `amplifier` command will be available and will use your local editable installations.

### Verify Installation

```bash
# Check amplifier is installed
amplifier --version

# List installed profiles
amplifier profile list

# Test with development profile
amplifier run --profile dev "Hello from development!"
```

---

## Dependency Management with uv

### Core Principles

1. **Never manually edit `pyproject.toml` dependencies** - always use `uv add`
2. **Each submodule manages its own dependencies** - no workspace configuration
3. **Lock files (`uv.lock`) are committed** - for reproducible builds
4. **Use `uv pip install -e .`** (not `pip`) for editable installs

### Adding Dependencies to a Module

**Navigate to the specific module**:

```bash
cd amplifier-module-provider-anthropic
```

**Add runtime dependency**:

```bash
uv add package-name

# Example:
uv add httpx
```

**Add development dependency**:

```bash
uv add --dev pytest
uv add --dev pytest-asyncio
```

**Update all dependencies**:

```bash
uv lock --upgrade
```

**What happens**:
- `pyproject.toml` is updated with the new dependency
- `uv.lock` is regenerated with pinned versions
- Both files should be committed to git

### Cross-Module Dependencies

When one module depends on another amplifier module, use **git URL dependencies** in `pyproject.toml`:

```toml
# amplifier-app-cli/pyproject.toml
[project]
dependencies = [
    "amplifier-core",
    "click>=8.1.0",
]

[tool.uv.sources]
amplifier-core = { git = "https://github.com/microsoft/amplifier-core", branch = "main" }
```

**Why git URLs?**
- Works for both local development and GitHub installation
- No need for PyPI publication
- Allows direct dependency on specific branches/commits

**For local development**, the install scripts override these with editable installs:

```bash
# After running install-dev.sh:
cd amplifier-app-cli
uv pip install -e ../amplifier-core  # Overrides git URL
```

### Common uv Commands

```bash
# Install project with dependencies
cd <module-dir>
uv pip install -e .

# Install with dev dependencies
uv sync --dev

# Add dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Update dependencies
uv lock --upgrade

# Run tests with dependencies
uv run pytest

# Run linters
uv run ruff check .
uv run ruff format .
```

---

## Git Workflow and Submodules

### Understanding the Structure

The `amplifier-dev` repository contains **git submodules** for each component:

```
amplifier-dev/              # Parent repository
├── amplifier-core/         # Submodule: kernel
├── amplifier-app-cli/      # Submodule: CLI application
├── amplifier-module-*/     # Submodules: various modules
├── amplifier-collection-*/ # Submodules: collections
└── amplifier/              # Submodule: FUTURE head (on 'next' branch)
```

**CRITICAL**: Each submodule is a **separate git repository**. Changes to files in a submodule only affect that submodule's repository.

### Working with Submodules

**Check submodule status**:

```bash
# From amplifier-dev root
git submodule status
```

**Update submodule to latest**:

```bash
cd amplifier-core
git pull origin main
cd ..

# Update parent to track new commit
git add amplifier-core
git commit -m "chore: update amplifier-core submodule"
```

**Make changes in a submodule**:

```bash
# Navigate to submodule
cd amplifier-module-provider-anthropic

# Make changes
git checkout -b feature/my-feature
# ... edit files ...
git add .
git commit -m "feat: add new capability"

# Push to submodule's repository
git push origin feature/my-feature

# Return to parent and update submodule pointer
cd ..
git add amplifier-module-provider-anthropic
git commit -m "chore: update provider-anthropic to feature branch"
```

### Branch Strategy

**Standard modules**: Develop on `main` branch

```bash
cd amplifier-core
git checkout main
```

**amplifier submodule**: Special case - develop on `next` branch

```bash
cd amplifier
git checkout next  # Not main!
```

The `amplifier` submodule represents the FUTURE head of the project and uses the `next` branch for development until ready to merge to `main`.

### Commit Message Guidelines

When creating commits, use this footer in your commit message:

```
feat: add new authentication module

This adds support for OAuth2 authentication...

🤖 Generated with [Amplifier](https://github.com/microsoft/amplifier)

Co-Authored-By: Amplifier <240397093+microsoft-amplifier@users.noreply.github.com>
```

---

## Custom Module Development

### Module Types

Amplifier supports six module types:

| Type | Purpose | Example |
|------|---------|---------|
| **Provider** | LLM backends | `provider-anthropic`, `provider-openai` |
| **Tool** | Agent capabilities | `tool-filesystem`, `tool-bash` |
| **Orchestrator** | Execution loops | `loop-basic`, `loop-streaming` |
| **Context** | Memory management | `context-simple`, `context-persistent` |
| **Hook** | Observability | `hooks-logging`, `hooks-approval` |
| **Agent** | Config overlays | User-defined agent personas |

### Creating a New Module

**1. Create module directory**:

```bash
cd amplifier-dev
mkdir amplifier-module-tool-myfeature
cd amplifier-module-tool-myfeature
```

**2. Initialize with uv**:

```bash
uv init
```

**3. Set up `pyproject.toml`**:

```toml
[project]
name = "amplifier-module-tool-myfeature"
version = "0.1.0"
description = "Custom tool module for Amplifier"
requires-python = ">=3.11"
dependencies = [
    # Add your dependencies
]

# Entry point for module discovery
[project.entry-points."amplifier.modules"]
tool-myfeature = "amplifier_module_tool_myfeature:mount"

[tool.uv.sources]
# No amplifier-core dependency - peer dependency pattern
```

**4. Create module implementation** (`amplifier_module_tool_myfeature/__init__.py`):

```python
"""Custom tool module for Amplifier."""

async def mount(coordinator, config):
    """Mount function called by kernel to load this module.

    Args:
        coordinator: Kernel coordinator providing access to hooks, context, etc.
        config: Dictionary of configuration from mount plan

    Returns:
        Tool instance implementing the Tool protocol
    """
    # Your tool implementation
    return MyFeatureTool(config)


class MyFeatureTool:
    """Tool implementation following amplifier-core Tool protocol."""

    def __init__(self, config: dict):
        self.config = config

    async def execute(self, input: dict) -> dict:
        """Execute the tool with given input.

        Args:
            input: Tool input dictionary

        Returns:
            Tool result dictionary with 'status' and 'data'
        """
        # Your tool logic here
        return {
            "status": "success",
            "data": {"result": "..."}
        }
```

**5. Add tests** (`tests/test_myfeature.py`):

```python
import pytest
from amplifier_module_tool_myfeature import mount

@pytest.mark.asyncio
async def test_tool_execution():
    """Test that tool executes successfully."""
    # Mock coordinator
    class MockCoordinator:
        pass

    tool = await mount(MockCoordinator(), {})
    result = await tool.execute({"arg": "value"})

    assert result["status"] == "success"
```

**6. Install in development mode**:

```bash
uv pip install -e .
```

**7. Test with amplifier**:

Create a test profile using your module:

```yaml
# ~/.amplifier/profiles/test-myfeature.md
---
extends: dev
---

# Test My Feature

Test profile for custom module.

```yaml
tools:
  - module: tool-myfeature
    source: file:///path/to/amplifier-module-tool-myfeature
    config:
      enabled: true
```
```

Test it:

```bash
amplifier run --profile test-myfeature "Use my feature"
```

### Module Development Workflow

**Typical workflow**:

1. **Create module skeleton** (directory, pyproject.toml, __init__.py)
2. **Implement mount function** and module class
3. **Add tests** (pytest with mocked coordinator)
4. **Install editable** (`uv pip install -e .`)
5. **Test with profile** using `file://` source
6. **Iterate**: Edit code → Test → Repeat (no reinstall needed)
7. **Publish**: Push to git repository, update profile to use `git+` source

---

## Custom Collection Development

### What is a Collection?

A **collection** bundles:
- **Agents**: Specialized AI personas (markdown with YAML frontmatter)
- **Tools**: CLI tools built with amplifier-core
- **Documentation**: Guides and examples

### Collection Structure

```
amplifier-collection-myname/
├── pyproject.toml              # Collection metadata
├── README.md                   # User guide
├── agents/                     # Agent definitions
│   ├── analyst.md
│   └── researcher.md
├── scenario-tools/             # CLI tools
│   └── my-analyzer/
│       ├── main.py
│       ├── pyproject.toml
│       └── README.md
└── docs/                       # Documentation
    └── GUIDE.md
```

### Creating a Collection

**1. Create collection directory**:

```bash
cd amplifier-dev
mkdir amplifier-collection-myname
cd amplifier-collection-myname
```

**2. Initialize with uv**:

```bash
uv init
```

**3. Set up `pyproject.toml`**:

```toml
[project]
name = "amplifier-collection-myname"
version = "0.1.0"
description = "Custom collection for Amplifier"
requires-python = ">=3.11"
dependencies = [
    "amplifier-core",
]

[tool.uv.sources]
amplifier-core = { git = "https://github.com/microsoft/amplifier-core", branch = "main" }

# Entry point for collection discovery
[project.entry-points."amplifier.collections"]
myname = "amplifier_collection_myname"
```

**4. Create agents** (`agents/analyst.md`):

```markdown
---
name: analyst
version: "1.0"
description: "Data analysis specialist"
providers:
  - module: provider-anthropic
    source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
    config:
      model: claude-sonnet-4-5
      temperature: 0.3
---

# Analyst Agent

You are an expert data analyst...

## Guidelines

1. Approach analysis systematically
2. Provide statistical evidence
3. Visualize findings when possible
```

**5. Create scenario tool** (`scenario-tools/my-analyzer/main.py`):

```python
"""Custom analysis tool."""

import asyncio
from pathlib import Path
from amplifier_core import AmplifierSession

# Tool configuration
ANALYZER_CONFIG = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple",
    },
    "providers": [{
        "module": "provider-anthropic",
        "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
        "config": {
            "model": "claude-sonnet-4-5",
            "temperature": 0.3,
        }
    }],
}

async def main():
    """Run analysis."""
    async with AmplifierSession(config=ANALYZER_CONFIG) as session:
        result = await session.execute("Analyze this data...")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

**6. Add tool packaging** (`scenario-tools/my-analyzer/pyproject.toml`):

```toml
[project]
name = "my-analyzer"
version = "0.1.0"
description = "Custom analysis tool"
requires-python = ">=3.11"
dependencies = [
    "amplifier-core",
]

[project.scripts]
my-analyzer = "my_analyzer.main:main"

[tool.uv.sources]
amplifier-core = { git = "https://github.com/microsoft/amplifier-core", branch = "main" }
```

**7. Install collection**:

```bash
# From collection root
uv pip install -e .

# Install scenario tool
cd scenario-tools/my-analyzer
uv pip install -e .
```

**8. Test collection**:

```bash
# Test agent loading
amplifier run --agent myname:analyst "Analyze this..."

# Test scenario tool
my-analyzer
```

---

## Local Testing

### Testing During Development

**CRITICAL**: When working in `amplifier-dev`, changes are immediately reflected due to editable installs.

```bash
cd amplifier-dev

# Make changes to any submodule
cd amplifier-module-tool-filesystem
# Edit files...

# Test immediately (no reinstall needed)
amplifier run --profile dev "Use filesystem tool"
```

**Why this works**:
- `.amplifier/settings.yaml` maps module names to local directories
- Install scripts installed all packages in editable mode (`-e`)
- Python imports directly from source directories

### Local Source Overrides

The development setup configures source overrides in `.amplifier/settings.yaml`:

```yaml
sources:
  # Core packages
  amplifier-core: file:///path/to/amplifier-dev/amplifier-core
  amplifier-app-cli: file:///path/to/amplifier-dev/amplifier-app-cli

  # Modules
  provider-anthropic: file:///path/to/amplifier-dev/amplifier-module-provider-anthropic
  tool-filesystem: file:///path/to/amplifier-dev/amplifier-module-tool-filesystem

  # Collections
  toolkit: file:///path/to/amplifier-dev/amplifier-collection-toolkit
```

This ensures the local versions are used instead of GitHub URLs.

### JSON Output for Automation

Test with JSON output for automation/scripting:

```bash
# Get structured JSON response
amplifier run --output-format json --profile dev "test prompt"

# Clean JSON for piping (suppress diagnostics)
amplifier run --output-format json "test" 2>/dev/null | jq .

# Capture JSON and diagnostics separately
amplifier run --output-format json "test" 1>response.json 2>diagnostics.log
```

**JSON Schema**:

```json
{
  "status": "success",
  "response": "AI response text",
  "session_id": "uuid",
  "profile": "profile-name",
  "model": "provider/model",
  "timestamp": "ISO8601"
}
```

### Interactive Testing

Test interactive features:

```bash
# Interactive mode
amplifier

# Within interactive mode:
/think              # Enable plan mode
/tools              # List available tools
/status             # Show session info
/profile dev        # Switch profile
```

### Running Test Suites

**Run module tests**:

```bash
cd amplifier-module-tool-filesystem
uv run pytest
uv run pytest -v  # Verbose
uv run pytest tests/test_specific.py  # Specific test
```

**Run verification tests** (after changes to CLI/libraries):

```bash
cd dev_verification

# Quick verification (~6 seconds, skip GitHub test)
SKIP_GITHUB_TEST=1 ./run_all_tests.sh

# Full verification (~3 minutes)
./run_all_tests.sh
```

**What gets tested**:
- All CLI commands work
- All libraries install from GitHub
- Toolkit collection utilities work
- Documentation examples are executable
- Dead code prevention

### Accessing Session Logs

**Session logs** are written to JSONL files:

```
~/.amplifier/projects/<project-slug>/sessions/<session-id>/events.jsonl
```

**Finding logs**:

```bash
# Find most recent session log
ls -lt ~/.amplifier/projects/*/sessions/*/events.jsonl | head -1

# View recent logs for current project
ls -lt ~/.amplifier/projects/<project-slug>/sessions/*/events.jsonl | head -5

# Grep for specific events
grep '"event":\s*"provider:request"' <log-file>

# Pretty-print event
grep '"event":\s*"llm:response:raw"' <log-file> | head -1 | python3 -m json.tool
```

**Debug logging**:

Enable detailed logging in profiles:

```yaml
hooks:
  - module: hooks-logging
    source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
    config:
      debug: true          # Emits llm:request:debug, llm:response:debug
      raw_debug: true      # Emits llm:request:raw, llm:response:raw (full API I/O)
```

---

## Packaging and Distribution

### Module Distribution

**1. Publish module to GitHub**:

```bash
cd amplifier-module-tool-myfeature
git remote add origin https://github.com/yourusername/amplifier-module-tool-myfeature
git push -u origin main
```

**2. Reference in profiles**:

```yaml
tools:
  - module: tool-myfeature
    source: git+https://github.com/yourusername/amplifier-module-tool-myfeature@main
    config:
      enabled: true
```

Users can now load your module via git URL (no PyPI needed).

### Collection Distribution

**1. Publish collection to GitHub**:

```bash
cd amplifier-collection-myname
git remote add origin https://github.com/yourusername/amplifier-collection-myname
git push -u origin main
```

**2. Users install with**:

```bash
# Install collection
amplifier collection add myname git+https://github.com/yourusername/amplifier-collection-myname@main

# Use collection agent
amplifier run --agent myname:analyst "Task description"

# Install scenario tool
uvx --from git+https://github.com/yourusername/amplifier-collection-myname@main my-analyzer
```

### Versioning

Use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes to module contracts
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

```toml
# pyproject.toml
[project]
version = "1.2.3"
```

Tag releases:

```bash
git tag v1.2.3
git push origin v1.2.3
```

Reference specific versions:

```yaml
source: git+https://github.com/yourusername/module@v1.2.3
```

---

## Debugging

### Enable Debug Logging

**In profiles**:

```yaml
hooks:
  - module: hooks-logging
    source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
    config:
      debug: true
      raw_debug: true  # Include full API requests/responses
```

**Via CLI flags** (if supported):

```bash
amplifier run --debug "prompt"
```

### Debugging Module Loading

**Check module discovery**:

```bash
amplifier module list
```

**Check source resolution**:

```bash
amplifier source list
```

**Manually test module loading**:

```python
# test_module_loading.py
import asyncio
from amplifier_core import create_kernel

async def test_load():
    mount_plan = {
        "session": {
            "orchestrator": "loop-basic",
            "context": "context-simple",
        },
        "tools": [{
            "module": "tool-myfeature",
            "source": "file:///path/to/amplifier-module-tool-myfeature",
            "config": {}
        }],
    }

    kernel = create_kernel()
    session = await kernel.create_session(mount_plan)
    print(f"Session created: {session.id}")
    print(f"Tools loaded: {list(session.tools.keys())}")

asyncio.run(test_load())
```

### Debugging Module Execution

**Add print statements**:

```python
# In your module
async def execute(self, input: dict) -> dict:
    print(f"Tool executing with input: {input}")  # Temporary debug
    result = do_work(input)
    print(f"Tool result: {result}")
    return result
```

**Use Python debugger**:

```python
import pdb; pdb.set_trace()  # Breakpoint
```

Run with:

```bash
python -m pdb your_tool.py
```

### Common Issues

**Issue: Module not found**

Check:
1. Module name matches entry point name in `pyproject.toml`
2. Module is installed (`uv pip list | grep myfeature`)
3. Source mapping exists (`.amplifier/settings.yaml` or profile)

**Issue: Import errors**

Check:
1. All dependencies are installed (`uv sync`)
2. Python version matches requirement (`python --version`)
3. Virtual environment is activated

**Issue: Changes not reflected**

Check:
1. Module installed in editable mode (`uv pip install -e .`)
2. Not accidentally using cached version
3. Source override pointing to correct directory

---

## Best Practices

### Code Organization

**Module structure**:

```
amplifier-module-tool-myfeature/
├── amplifier_module_tool_myfeature/
│   ├── __init__.py         # mount() function
│   ├── core.py             # Main implementation
│   ├── utils.py            # Helper functions
│   └── config.py           # Configuration models
├── tests/
│   ├── test_core.py
│   └── test_utils.py
├── pyproject.toml
├── README.md
└── LICENSE
```

**Collection structure**:

```
amplifier-collection-myname/
├── amplifier_collection_myname/
│   └── __init__.py         # Collection metadata
├── agents/                 # Agent definitions
│   ├── analyst.md
│   └── researcher.md
├── scenario-tools/         # CLI tools
│   └── my-analyzer/
│       ├── my_analyzer/
│       │   └── main.py
│       ├── pyproject.toml
│       └── README.md
├── docs/                   # Documentation
│   └── GUIDE.md
├── pyproject.toml
├── README.md
└── LICENSE
```

### Documentation

**Module README template**:

```markdown
# amplifier-module-tool-myfeature

Description of what this module does.

## Installation

\`\`\`bash
amplifier module add tool-myfeature git+https://github.com/user/repo@main
\`\`\`

## Usage

\`\`\`yaml
tools:
  - module: tool-myfeature
    source: git+https://github.com/user/repo@main
    config:
      option: value
\`\`\`

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| option | str  | "value" | What it does |

## Examples

...
```

### Testing

**Test module contracts**:

```python
@pytest.mark.asyncio
async def test_mount_returns_tool():
    """Verify mount function returns object with execute method."""
    tool = await mount(MockCoordinator(), {})
    assert hasattr(tool, 'execute')
    assert callable(tool.execute)

@pytest.mark.asyncio
async def test_execute_returns_result():
    """Verify execute returns dict with status and data."""
    tool = await mount(MockCoordinator(), {})
    result = await tool.execute({"test": "input"})
    assert "status" in result
    assert "data" in result
```

### Version Control

**.gitignore**:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/

# uv
uv.lock

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Amplifier
.amplifier/settings.yaml  # Local settings only
```

**Commit frequently**:

```bash
git add .
git commit -m "feat: add feature X"
git push
```

Use conventional commit messages:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks
- `test:` - Test additions/changes

---

## Troubleshooting

### "Module not found" Error

**Symptoms**: `amplifier` can't find your module

**Solutions**:

1. **Check module is installed**:

```bash
uv pip list | grep myfeature
```

If not listed, install it:

```bash
cd amplifier-module-tool-myfeature
uv pip install -e .
```

2. **Check entry point** in `pyproject.toml`:

```toml
[project.entry-points."amplifier.modules"]
tool-myfeature = "amplifier_module_tool_myfeature:mount"
```

3. **Check source mapping**:

Either in profile:

```yaml
tools:
  - module: tool-myfeature
    source: file:///path/to/module
```

Or in `.amplifier/settings.yaml`:

```yaml
sources:
  tool-myfeature: file:///path/to/module
```

### "Import errors" in Module

**Symptoms**: Module fails to import dependencies

**Solutions**:

1. **Install dependencies**:

```bash
cd your-module
uv sync
```

2. **Check pyproject.toml dependencies**:

```toml
[project]
dependencies = [
    "required-package>=1.0.0",
]
```

3. **Verify Python version**:

```bash
python --version
# Should match requires-python in pyproject.toml
```

### Changes Not Reflected

**Symptoms**: Code changes don't show up when running

**Solutions**:

1. **Verify editable install**:

```bash
uv pip show amplifier-module-tool-myfeature
# Should show: Location: /path/to/module (in editable mode)
```

2. **Reinstall in editable mode**:

```bash
cd your-module
uv pip uninstall amplifier-module-tool-myfeature
uv pip install -e .
```

3. **Check source override** points to correct directory:

```yaml
# .amplifier/settings.yaml
sources:
  tool-myfeature: file:///correct/path/to/module
```

### Submodule Confusion

**Symptoms**: Git operations affect wrong repository

**Solutions**:

1. **Always check where you are**:

```bash
pwd  # Should show submodule directory
git remote -v  # Should show submodule repository
```

2. **Commit in submodule first, then parent**:

```bash
# In submodule
cd amplifier-module-tool-myfeature
git add .
git commit -m "feat: add feature"
git push

# In parent
cd ..
git add amplifier-module-tool-myfeature
git commit -m "chore: update submodule pointer"
git push
```

3. **Update submodules** before making changes:

```bash
git submodule update --remote
```

---

## Related Guides

- [**Modules Guide**](./modules.md) - Module types, contracts, and discovery
- [**Profiles Guide**](./profiles.md) - Profile system and configuration
- [**CLI Guide**](./cli.md) - CLI commands and usage
- [**Mounts Guide**](./mounts.md) - Mount plans and module loading

---

## Summary

This guide covered:

1. **Environment setup** - Installing uv, cloning repositories, running install scripts
2. **Dependency management** - Using uv for adding dependencies and managing lock files
3. **Git workflow** - Working with submodules, branches, and commits
4. **Module development** - Creating custom tools, providers, contexts, etc.
5. **Collection development** - Bundling agents, tools, and documentation
6. **Local testing** - Testing during development with editable installs
7. **Packaging** - Publishing modules and collections to GitHub
8. **Debugging** - Enabling debug logs, testing module loading, troubleshooting

**Key takeaways**:

- Use `uv` for all dependency management
- Each submodule is a separate git repository
- Install with `uv pip install -e .` for immediate reflection of changes
- Test locally with `file://` sources before publishing
- Publish to GitHub with git URLs (no PyPI needed)
- Follow semantic versioning for releases

For more information, see the [Amplifier documentation](https://github.com/microsoft/amplifier-dev).
