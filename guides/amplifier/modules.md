# Amplifier Modules Guide

**Comprehensive technical guide for developers working with Amplifier modules**

---

## Table of Contents

1. [What Are Modules?](#what-are-modules)
2. [The Six Module Types](#the-six-module-types)
3. [Module Contracts](#module-contracts)
4. [Module Discovery](#module-discovery)
5. [Module Mounting](#module-mounting)
6. [Creating Your Own Module](#creating-your-own-module)
7. [Module Examples](#module-examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Modules?

Amplifier uses a modular philosophy inspired by the Linux Kernel:

- **Kernel (amplifier-core)**: Ultra-thin, stable, provides MECHANISMS only
- **Modules**: Self-contained "bricks" with stable interface "studs"
- **Principle**: "The center stays still so the edges can move fast"

### Key Concepts

**Mechanism vs Policy**:
- **Mechanism** (kernel): How to load, coordinate, execute modules
- **Policy** (modules): Which provider, what tools, when to use them

**Non-Interference**:
- Failing module cannot crash the kernel
- Modules are isolated from each other
- Graceful degradation always

**Stable Boundaries**:
- Module interfaces (protocols) rarely change
- Modules can be swapped without kernel changes
- Backward compatibility is sacred

---

## The Six Module Types

### 1. Provider - LLM Backends

**Purpose**: Interface to language models (Anthropic, OpenAI, Azure, Ollama, Mock)

**Contract**:
```python
class Provider:
    async def complete(
        messages: list[dict],
        tools: list[Tool] | None = None,
        **kwargs
    ) -> ProviderResponse

    def parse_tool_calls(response: ProviderResponse) -> list[ToolCall]
```

**Examples**: `provider-anthropic`, `provider-openai`, `provider-azure-openai`, `provider-mock`

### 2. Tool - Agent Capabilities

**Purpose**: Actions the AI can take (filesystem, bash, web, search, task delegation)

**Contract**:
```python
class Tool:
    async def execute(input: dict[str, Any]) -> ToolResult
```

**Examples**: `tool-filesystem`, `tool-bash`, `tool-web`, `tool-search`, `tool-task`, `tool-todo`

### 3. Orchestrator - Execution Loops

**Purpose**: Strategy for executing prompts and managing tool calls

**Contract**:
```python
class Orchestrator:
    async def execute(
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: HookRegistry,
        coordinator: ModuleCoordinator | None = None
    ) -> str
```

**Examples**: `loop-basic`, `loop-streaming`, `loop-events`

### 4. Context - Memory Management

**Purpose**: Store and manage conversation history, implement compaction strategies

**Contract**:
```python
class ContextManager:
    async def add_message(message: dict) -> None
    async def get_messages() -> list[dict]
    async def should_compact() -> bool
    async def compact() -> None
    async def clear() -> None
```

**Examples**: `context-simple`, `context-persistent`

### 5. Hook - Observability & Control

**Purpose**: Observe events, inject context, request approvals, log activities

**Contract**:
```python
class HookHandler:
    async def __call__(
        event: str,
        data: dict[str, Any]
    ) -> HookResult
```

**Examples**: `hooks-logging`, `hooks-redaction`, `hooks-approval`, `hooks-status-context`, `hooks-streaming-ui`

### 6. Agent - Config Overlays

**Purpose**: Sub-session configurations for task delegation (NOT a module type, but configuration)

**Format**: Markdown files with YAML frontmatter specifying provider/tool/hook overrides

**Examples**: `zen-architect`, `bug-hunter`, `modular-builder`

---

## Module Contracts

Each module type implements a Python protocol defining its interface:

### Provider Protocol

```python
from amplifier_core import ProviderResponse

class Provider(Protocol):
    """LLM backend interface."""

    async def complete(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
        **kwargs
    ) -> ProviderResponse:
        """Generate completion from messages."""
        ...

    def parse_tool_calls(
        self,
        response: ProviderResponse
    ) -> list[ToolCall]:
        """Extract tool calls from response."""
        ...
```

### Tool Protocol

```python
from amplifier_core import ToolResult

class Tool(Protocol):
    """Agent capability interface."""

    async def execute(
        self,
        input: dict[str, Any]
    ) -> ToolResult:
        """Execute tool with given input."""
        ...
```

### Orchestrator Protocol

```python
class Orchestrator(Protocol):
    """Execution loop interface."""

    async def execute(
        self,
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: HookRegistry,
        coordinator: ModuleCoordinator | None = None
    ) -> str:
        """Execute prompt and return response."""
        ...
```

### Context Protocol

```python
class ContextManager(Protocol):
    """Memory management interface."""

    async def add_message(self, message: dict) -> None:
        """Add message to history."""
        ...

    async def get_messages(self) -> list[dict]:
        """Retrieve all messages."""
        ...

    async def should_compact(self) -> bool:
        """Check if compaction needed."""
        ...

    async def compact(self) -> None:
        """Compact message history."""
        ...

    async def clear(self) -> None:
        """Clear all messages."""
        ...
```

### Hook Protocol

```python
from amplifier_core import HookResult

class HookHandler(Protocol):
    """Observability hook interface."""

    async def __call__(
        self,
        event: str,
        data: dict[str, Any]
    ) -> HookResult:
        """Process event and return action."""
        ...
```

---

## Module Discovery

Modules are discovered via two mechanisms:

### 1. Entry Points (Primary)

Defined in `pyproject.toml`:

```toml
[project.entry-points."amplifier.modules"]
provider-anthropic = "amplifier_module_provider_anthropic:mount"
tool-filesystem = "amplifier_module_tool_filesystem:mount"
```

**Format**: `module-id = "package.module:mount_function"`

### 2. Filesystem Discovery (Fallback)

Set via environment variable:

```bash
export AMPLIFIER_MODULES=/path/to/modules:/another/path
```

The loader searches for Python packages with `mount()` functions.

---

## Module Mounting

### The mount() Function

Every module must implement:

```python
async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any] | None = None
) -> Callable | None:
    """
    Mount module and return cleanup function.

    Args:
        coordinator: Central coordination hub
        config: Module-specific configuration

    Returns:
        Optional cleanup function
    """
    # 1. Create module instance with config
    module = MyModule(config or {})

    # 2. Mount to coordinator
    await coordinator.mount("mount_point", module)

    # 3. Register capabilities (optional)
    coordinator.register_capability("my.capability", module.do_something)

    # 4. Return cleanup function
    def cleanup():
        # Close resources, unregister, etc.
        pass

    return cleanup
```

### Mount Points

The coordinator manages these mount points:

| Mount Point | Cardinality | Purpose |
|-------------|-------------|---------|
| `orchestrator` | Single | Execution loop |
| `context` | Single | Memory management |
| `providers` | Multiple (dict) | LLM backends |
| `tools` | Multiple (dict) | Agent capabilities |
| `hooks` | Multiple (registry) | Observability |

### Mounting Flow

```
Profile specifies module
    ↓
ModuleLoader.load(module_id, config, source)
    ↓
Discover via entry points or filesystem
    ↓
Import module and call mount(coordinator, config)
    ↓
Module mounts itself at appropriate point
    ↓
Returns cleanup function (or None)
    ↓
Coordinator registers cleanup for session end
```

---

## Creating Your Own Module

### Step 1: Define Purpose and Type

Decide:
- What type of module? (provider, tool, hook, etc.)
- What problem does it solve?
- What interface (protocol) must it implement?

### Step 2: Create Module Structure

```bash
# Create new module with uv
uv init --lib amplifier-module-tool-example
cd amplifier-module-tool-example

# Structure:
# amplifier-module-tool-example/
# ├── amplifier_module_tool_example/
# │   └── __init__.py
# ├── pyproject.toml
# ├── README.md
# └── tests/
```

### Step 3: Implement Module

Example tool module:

```python
# amplifier_module_tool_example/__init__.py
import logging
from typing import Any
from amplifier_core import ModuleCoordinator, ToolResult

logger = logging.getLogger(__name__)


class ExampleTool:
    """Example tool implementation."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.setting = config.get("setting", "default")

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """Execute the tool."""
        try:
            # Your tool logic here
            result = f"Executed with {input}"

            return ToolResult(
                success=True,
                output=result
            )
        except Exception as e:
            logger.error(f"Tool failed: {e}")
            return ToolResult(
                success=False,
                error={"message": str(e)}
            )


async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any] | None = None
) -> None:
    """Mount the example tool."""
    config = config or {}

    # Create tool instance
    tool = ExampleTool(config)

    # Mount to coordinator
    await coordinator.mount("tools", tool, name="example")

    logger.info("Mounted ExampleTool")

    # No cleanup needed
    return None
```

### Step 4: Add Entry Point

In `pyproject.toml`:

```toml
[project]
name = "amplifier-module-tool-example"
version = "0.1.0"
dependencies = ["amplifier-core"]

[project.entry-points."amplifier.modules"]
tool-example = "amplifier_module_tool_example:mount"
```

### Step 5: Test Locally

Set environment variable to include your module:

```bash
export AMPLIFIER_MODULES=/path/to/amplifier-module-tool-example
amplifier module list  # Should show tool-example
```

Or install in editable mode:

```bash
uv pip install -e /path/to/amplifier-module-tool-example
```

### Step 6: Publish

Push to GitHub and reference in profiles:

```yaml
tools:
  - module: tool-example
    source: git+https://github.com/yourorg/amplifier-module-tool-example@main
```

---

## Module Examples

### Provider Example

**Location**: `amplifier-module-provider-anthropic/`

**Key Implementation**:
```python
class AnthropicProvider:
    def __init__(self, config: dict):
        self.client = anthropic.AsyncAnthropic(api_key=config["api_key"])
        self.default_model = config.get("default_model", "claude-sonnet-4-5")

    async def complete(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
        **kwargs
    ) -> ProviderResponse:
        # Convert to Anthropic format
        response = await self.client.messages.create(
            model=kwargs.get("model", self.default_model),
            messages=messages,
            tools=[self._convert_tool(t) for t in tools] if tools else None,
            **kwargs
        )

        return ProviderResponse(
            content=response.content[0].text if response.content else "",
            content_blocks=[...],
            raw=response
        )
```

### Tool Example

**Location**: `amplifier-module-tool-filesystem/`

**Key Insight**: One module can provide multiple tools!

```python
async def mount(coordinator: ModuleCoordinator, config: dict | None = None):
    """Mount filesystem tools."""
    config = config or {}

    # Mount multiple tools from one module
    await coordinator.mount("tools", ReadFileTool(config), name="read")
    await coordinator.mount("tools", WriteFileTool(config), name="write")
    await coordinator.mount("tools", EditFileTool(config), name="edit")

    logger.info("Mounted filesystem tools: read, write, edit")
```

### Orchestrator Example

**Location**: `amplifier-module-loop-streaming/`

**Key Implementation**:
```python
class StreamingOrchestrator:
    async def execute(
        self,
        prompt: str,
        context: ContextManager,
        providers: dict[str, Provider],
        tools: dict[str, Tool],
        hooks: HookRegistry,
        coordinator: ModuleCoordinator | None = None
    ) -> str:
        # Add user message
        await context.add_message({"role": "user", "content": prompt})

        # Select provider
        provider = self._select_provider(providers)

        # Agent loop
        while True:
            # Get messages
            messages = await context.get_messages()

            # Call LLM
            response = await provider.complete(messages, tools=list(tools.values()))

            # Parse tool calls
            tool_calls = provider.parse_tool_calls(response)

            if not tool_calls:
                # No tools, return response
                await context.add_message({"role": "assistant", "content": response.content})
                return response.content

            # Execute tools in parallel
            results = await asyncio.gather(
                *[tools[tc.tool].execute(tc.arguments) for tc in tool_calls]
            )

            # Add tool results to context
            for tc, result in zip(tool_calls, results):
                await context.add_message({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result.output) if result.success else f"Error: {result.error}"
                })

            # Continue loop (LLM sees tool results)
```

---

## Best Practices

### 1. Follow the Protocol Exactly

**Don't**:
```python
async def execute(self, input):  # Missing type hints
    return "result"  # Wrong return type
```

**Do**:
```python
async def execute(self, input: dict[str, Any]) -> ToolResult:
    return ToolResult(success=True, output="result")
```

### 2. Never Raise Exceptions from Core Methods

**Don't**:
```python
async def execute(self, input):
    result = risky_operation()  # Could raise!
    return ToolResult(success=True, output=result)
```

**Do**:
```python
async def execute(self, input: dict[str, Any]) -> ToolResult:
    try:
        result = risky_operation()
        return ToolResult(success=True, output=result)
    except Exception as e:
        logger.error(f"Tool failed: {e}")
        return ToolResult(success=False, error={"message": str(e)})
```

### 3. Make Modules Configurable

**Don't**:
```python
class MyTool:
    def __init__(self):
        self.timeout = 30  # Hardcoded
```

**Do**:
```python
class MyTool:
    def __init__(self, config: dict[str, Any]):
        self.timeout = config.get("timeout", 30)  # Configurable with default
```

### 4. Clean Up Resources

**Don't**:
```python
async def mount(coordinator, config):
    tool = MyTool(config)
    await coordinator.mount("tools", tool, name="my-tool")
    # No cleanup!
```

**Do**:
```python
async def mount(coordinator, config):
    tool = MyTool(config)
    await coordinator.mount("tools", tool, name="my-tool")

    def cleanup():
        tool.close_connections()
        tool.cleanup_temp_files()

    return cleanup
```

### 5. Use Logging

**Do**:
```python
import logging
logger = logging.getLogger(__name__)

async def mount(coordinator, config):
    logger.info("Mounting MyTool")
    # ...
    logger.debug(f"Config: {config}")
```

### 6. Document Configuration Options

In module README:

```markdown
## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `timeout` | int | 30 | Request timeout in seconds |
| `retries` | int | 3 | Number of retry attempts |
```

---

## Troubleshooting

### Module Not Found

**Error**: `Module 'tool-xyz' not found`

**Check**:
1. Entry point is registered in `pyproject.toml`
2. Package is installed (`uv pip list`)
3. `AMPLIFIER_MODULES` includes module path (if using filesystem discovery)

**Debug**:
```bash
amplifier module list  # See discovered modules
python -c "from amplifier_module_tool_xyz import mount"  # Test import
```

### Module Fails to Mount

**Error**: `Failed to mount module 'tool-xyz': ...`

**Check**:
1. `mount()` function signature is correct
2. No exceptions raised during mount
3. Config is valid (check schema)
4. Dependencies are installed

**Debug**:
```python
# Test mount directly
from amplifier_core import ModuleCoordinator
from amplifier_module_tool_xyz import mount

coordinator = ModuleCoordinator(session_id="test", config={})
await mount(coordinator, {"key": "value"})
```

### Module Behavior Issues

**Issue**: Module loaded but not working as expected

**Check**:
1. Protocol implementation matches exactly
2. Return types are correct
3. Error handling is graceful
4. Logging shows what's happening

**Debug**:
```bash
# Run with verbose logging
amplifier run --verbose "test prompt"

# Check session events
cat ~/.amplifier/projects/*/sessions/*/events.jsonl | grep tool:execute
```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| Core interfaces | `amplifier-core/amplifier_core/interfaces.py` |
| Module loader | `amplifier-core/amplifier_core/loader.py` |
| Module coordinator | `amplifier-core/amplifier_core/coordinator.py` |
| Component catalog | `amplifier-core/docs/MODULES.md` |
| Module development guide | `amplifier-core/docs/MODULE_DEVELOPMENT.md` |

### Example Modules

| Module | Type | Location |
|--------|------|----------|
| provider-anthropic | Provider | `amplifier-module-provider-anthropic/` |
| provider-openai | Provider | `amplifier-module-provider-openai/` |
| tool-filesystem | Tool | `amplifier-module-tool-filesystem/` |
| tool-bash | Tool | `amplifier-module-tool-bash/` |
| tool-web | Tool | `amplifier-module-tool-web/` |
| loop-streaming | Orchestrator | `amplifier-module-loop-streaming/` |
| context-simple | Context | `amplifier-module-context-simple/` |
| hooks-logging | Hook | `amplifier-module-hooks-logging/` |

### Related Guides

- [**Profiles Guide**](./profiles.md) - How to configure modules via profiles
- [**Mounts Guide**](./mounts.md) - How mount plans specify modules
- [**CLI Guide**](./cli.md) - Using modules via CLI
- [**Development Guide**](./development.md) - Creating custom modules and collections

---

## Quick Reference

### Module Types Summary

| Type | Purpose | Cardinality | Example |
|------|---------|-------------|---------|
| Provider | LLM backend | Multiple | provider-anthropic |
| Tool | Capability | Multiple | tool-filesystem |
| Orchestrator | Execution loop | Single | loop-streaming |
| Context | Memory | Single | context-simple |
| Hook | Observability | Multiple | hooks-logging |

### Creating a Module Checklist

- [ ] Define purpose and type
- [ ] Create with `uv init --lib`
- [ ] Implement protocol interface
- [ ] Add `mount()` function
- [ ] Register entry point in pyproject.toml
- [ ] Test locally with `AMPLIFIER_MODULES`
- [ ] Add configuration options
- [ ] Write tests
- [ ] Document configuration
- [ ] Publish to GitHub
- [ ] Reference in profiles with `source: git+https://...`

---

**For more information**, see the [Module Development Guide](../amplifier-core/docs/MODULE_DEVELOPMENT.md).
