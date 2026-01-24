# Profiles (Legacy)

> **⚠️ DEPRECATED**: The profile system has been replaced by the simpler **bundle system**.
> See [Bundles](bundles.md) for the current approach.
>
> This documentation is preserved for historical reference and migration purposes.

**Reusable configuration templates for Amplifier sessions**

---

## What is a Profile?

A profile is a **configuration template** that defines everything an Amplifier session needs to run:

- **Which modules to load**: orchestrator, context manager, providers, tools, hooks
- **How to configure them**: model names, API keys, behavior settings
- **What agents to include**: AI personas with specific expertise
- **What context to provide**: Documentation and reference materials

**Think of it as:** A recipe for an AI session. Just like a recipe lists ingredients and steps, a profile lists modules and configurations.

---

## Profile Structure

Profiles are **markdown files with YAML frontmatter**:

```markdown
---
profile:
  name: base
  version: 1.0.0
  description: General-purpose profile

session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/org/modules@main
    config:
      extended_thinking: true
  context:
    module: context-simple
    source: git+https://github.com/org/modules@main

providers:
- module: provider-anthropic
  source: git+https://github.com/org/modules@main
  config:
    default_model: claude-sonnet-4-5

tools:
- module: tool-web
  source: git+https://github.com/org/modules@main

hooks:
- module: hooks-logging
  source: git+https://github.com/org/modules@main

agents:
  code-expert: https://example.com/agents/code.md

context:
  docs: git+https://github.com/org/docs@main#subdirectory=guides
---

# Base Profile

This profile provides a solid foundation for general-purpose AI work...
```

**Two parts:**
1. **YAML frontmatter** (between `---` markers): Configuration
2. **Markdown body**: Human-readable description

---

## Profile Identity

Profiles are identified by **collection/profile** naming:

```
foundation/base     → Collection: foundation, Profile: base
myteam/coding       → Collection: myteam, Profile: coding
experiments/fast    → Collection: experiments, Profile: fast
```

**Why this format?**
- **Namespacing**: Different teams can have profiles with same names
- **Organization**: Group related profiles in collections
- **Clarity**: Immediately know where a profile comes from

---

## What Profiles Contain

### Session Configuration (Required)

**Orchestrator** - The execution loop that runs the agent:
```yaml
session:
  orchestrator:
    module: loop-streaming        # Module ID
    source: git+https://github... # Where to get it
    config:                       # Module-specific config
      extended_thinking: true
      max_iterations: 10
```

**Context** - Memory and conversation management:
```yaml
session:
  context:
    module: context-simple
    source: git+https://github...
    config:
      max_tokens: 400000
      auto_compact: true
```

### Providers (Required, 1+)

**LLM providers** - Which AI models to use:
```yaml
providers:
- module: provider-anthropic
  source: git+https://github...
  config:
    default_model: claude-sonnet-4-5
    api_key: ${ANTHROPIC_API_KEY}  # Environment variable
```

**At least one provider required** for the session to function.

### Tools (Optional)

**Capabilities** the AI can use:
```yaml
tools:
- module: tool-web           # Web search
  source: git+https://github...
- module: tool-filesystem    # File operations
  source: git+https://github...
- module: tool-code          # Code analysis
  source: git+https://github...
```

### Hooks (Optional)

**Lifecycle extensions** - Run code at specific events:
```yaml
hooks:
- module: hooks-logging      # Log all events
  source: git+https://github...
  config:
    log_level: info
- module: hooks-redaction    # Redact sensitive data
  source: git+https://github...
```

### Agents (Optional)

**AI personas** - Specialized instructions for different roles:
```yaml
agents:
  code-expert: https://raw.githubusercontent.com/.../code-expert.md
  debug-helper: https://raw.githubusercontent.com/.../debug.md
  architect: file:///local/path/architect.md
```

**Formats supported:**
- `https://` URLs (raw markdown)
- `file://` paths (local files)
- `git+https://...#subdirectory=path` (from git repos)

### Context (Optional)

**Documentation directories** loaded on-demand via @mentions:
```yaml
context:
  docs: git+https://github.com/org/docs@main#subdirectory=guides
  api-ref: https://api.example.com/docs/
```

**Usage:**
```
User: @docs:API_GUIDE.md how do I authenticate?
```

The context system loads the file and injects it into the conversation.

---

## Module References

Profiles **reference** external modules - they don't contain them inline.

**Supported formats:**

**Git repositories:**
```yaml
source: git+https://github.com/org/repo@v1.0.0
source: git+https://github.com/org/repo@main
source: git+https://github.com/org/repo@abc123def456
```

**Git subdirectories:**
```yaml
source: git+https://github.com/org/repo@v1.0.0#subdirectory=modules/tool-web
```

**Local paths (development):**
```yaml
source: file:///absolute/path/to/module
```

**HTTP/HTTPS (for agents and context):**
```yaml
source: https://raw.githubusercontent.com/org/repo/main/agent.md
```

---

## Profile Naming Conventions

**Collection names:**
- Lowercase, hyphen-separated
- Examples: `foundation`, `my-team`, `experiments`

**Profile names:**
- Lowercase, hyphen-separated
- Examples: `base`, `coding`, `production`

**Full profile ID:**
```
{collection}/{profile}

foundation/base
my-team/coding-advanced
experiments/fast-iteration
```

---

## Module Naming Conventions

**Module IDs** (hyphenated, user-facing):
```
loop-streaming
provider-anthropic
tool-web
hooks-logging
```

**Package names** (underscored, Python):
```
amplifier_module_loop_streaming
amplifier_module_provider_anthropic
amplifier_module_tool_web
amplifier_module_hooks_logging
```

**Automatic conversion:**
- Profile says: `module: loop-streaming`
- Python imports: `amplifier_module_loop_streaming`
- ModuleLoader handles the conversion

---

## Profile Inheritance

Profiles can **extend** other profiles:

```yaml
---
profile:
  name: production
  extends: base              # Inherit from base profile

# Override specific settings
session:
  orchestrator:
    config:
      extended_thinking: false  # Override base's setting

# Add additional providers
providers:
- module: provider-azure      # Added to base's providers
  source: git+https://github...
---
```

**How it works:**
1. Load base profile configuration
2. Merge with current profile (deep merge)
3. Current profile values override base values
4. Arrays are concatenated (providers, tools, hooks)

---

## Real Example: foundation/base

**Location:** `registry/profiles/foundation/base.md`

```yaml
---
profile:
  name: base
  version: 1.1.0
  description: Base configuration with core functionality
  schema_version: 2

session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main
    config:
      extended_thinking: true
      max_iterations: 25

  context:
    module: context-simple
    source: git+https://github.com/microsoft/amplifier-module-context-simple@main
    config:
      max_tokens: 400000
      compact_threshold: 0.8

providers:
- module: provider-anthropic
  source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
  config:
    default_model: claude-sonnet-4-5

tools:
- module: tool-web
  source: git+https://github.com/microsoft/amplifier-module-tool-web@main
- module: tool-filesystem
  source: git+https://github.com/microsoft/amplifier-module-tool-filesystem@main

hooks:
- module: hooks-logging
  source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
  config:
    mode: session-only

agents:
  explorer: https://raw.githubusercontent.com/org/agents/main/explorer.md

context:
  foundation: git+https://github.com/org/docs@main#subdirectory=foundation
---

# Base Profile

General-purpose profile suitable for most workflows. Includes core tools,
standard agents, and sensible defaults for context management.

## What's Included

- **Orchestrator**: Streaming loop with extended thinking
- **Context**: Simple context manager with auto-compaction
- **Provider**: Anthropic Claude (Sonnet 4.5)
- **Tools**: Web search, filesystem operations
- **Agents**: General-purpose explorer agent
- **Hooks**: Session logging for debugging

## When to Use

- Starting a new workflow and unsure which profile to use
- General coding, research, or writing tasks
- Need a solid foundation to customize from

## Customization

Extend this profile to add your own:
- Additional tools
- Specialized agents
- Custom hooks
- Different providers
```

---

## Profile Validation Rules

**Required fields:**
- `profile.name`
- `session.orchestrator`
- `session.context`
- At least one provider

**Optional fields:**
- `tools` (defaults to empty array)
- `hooks` (defaults to empty array)
- `agents` (defaults to empty dict)
- `context` (defaults to empty dict)

**Validation happens:**
- When generating mount plans (structure check)
- When initializing sessions (runtime check)

---

## Where Profiles Live

**Source definitions:**
```
registry/profiles/{collection}/{profile}.md
```

**After compilation:**
```
.amplifierd/share/profiles/{collection}/{profile}/
├── profile.md           (copy of source)
├── profile.lock         (change detection)
├── orchestrator/
├── context/
├── providers/
├── tools/
├── hooks/
├── agents/
└── contexts/
```

**Why two locations?**
- **registry/**: Source of truth (version controlled)
- **.amplifierd/share/**: Compiled resources (runtime cache)

---

## Next Steps

**Understand mount plans:**
- Read [Mount Plans](mount-plans.md) to see what profiles become

**See the full transformation:**
- Read [Profile Lifecycle](../04-advanced/profile-lifecycle.md)

**Create your first profile:**
- Copy `foundation/base.md` as a template
- Customize modules and agents
- Add to collections.yaml
- Compile and test
