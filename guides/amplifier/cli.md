# Amplifier CLI Guide

**Comprehensive technical guide for developers working with the Amplifier CLI**

---

## Table of Contents

1. [What Is the CLI?](#what-is-the-cli)
2. [Architecture](#architecture)
3. [Command Categories](#command-categories)
4. [Session Management](#session-management)
5. [Configuration Management](#configuration-management)
6. [Interactive Mode](#interactive-mode)
7. [Output Formats](#output-formats)
8. [Development Patterns](#development-patterns)
9. [Troubleshooting](#troubleshooting)
10. [Logging and Inspection](#logging-and-inspection)
11. [Reference](#reference)

---

## What Is the CLI?

The **Amplifier CLI** (`amplifier-app-cli`) is a reference implementation of a command-line interface built on top of **amplifier-core**. It demonstrates how to build user-facing applications around the kernel.

### Key Characteristics

- **Reference implementation**: You can use as-is, fork, or build your own
- **Kernel-first**: Thin layer around amplifier-core mechanisms
- **Profile-driven**: Configuration via reusable profile system
- **Module-agnostic**: Works with any modules following kernel contracts
- **Session-centric**: Persistent conversational sessions with resume capability

### Philosophy

The CLI follows the "policy at edges" principle:
- **Kernel (amplifier-core)**: Provides mechanisms (loading, coordinating, executing)
- **CLI (amplifier-app-cli)**: Provides policies (which modules, when to use them, UX)
- **User**: Controls everything through profiles, configuration, and commands

---

## Architecture

### Component Stack

```
┌─────────────────────────────────────────┐
│  CLI Commands                           │  User-facing commands
│  (profile, session, module, etc.)       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Configuration Layer                    │
│  - amplifier-profiles (loading)         │
│  - amplifier-config (settings)          │
│  - amplifier-module-resolution (sources)│
│  - amplifier-collections (bundles)      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Session Management                     │
│  - SessionStore (persistence)           │
│  - SessionSpawner (agent delegation)    │
│  - Context loading (@mentions)          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Kernel (amplifier-core)                │
│  - AmplifierSession                     │
│  - ModuleCoordinator                    │
│  - HookRegistry                         │
└─────────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **main.py** | CLI entry point | `amplifier_app_cli/main.py` |
| **commands/** | Command implementations | `amplifier_app_cli/commands/` |
| **session_store.py** | Session persistence | `amplifier_app_cli/session_store.py` |
| **session_spawner.py** | Agent delegation | `amplifier_app_cli/session_spawner.py` |
| **mention_loading/** | @mention expansion | `amplifier_app_cli/lib/mention_loading/` |
| **data/** | Bundled collections/profiles | `amplifier_app_cli/data/` |

---

## Command Categories

### 1. Execution Commands

**Purpose**: Run prompts and interact with agents

```bash
# Single-shot execution
amplifier run "Your prompt here"
amplifier run --profile dev "Your prompt"
amplifier run --output-format json "Your prompt"

# Interactive mode (REPL)
amplifier
amplifier --profile full
amplifier --mode chat

# Resume sessions
amplifier continue                      # Resume most recent
amplifier continue "new prompt"          # Resume with new prompt
amplifier run --resume <session-id> "prompt"  # Resume specific session
```

**Key flags**:
- `--profile <name>`: Use specific profile
- `--output-format json`: JSON output for automation
- `--mode chat`: Force interactive mode
- `--resume <id>`: Resume specific session

### 2. Session Commands

**Purpose**: Manage conversation sessions

```bash
# List sessions
amplifier session list                  # Recent sessions
amplifier session list --all            # All sessions
amplifier session list --days 7         # Last 7 days

# Show session details
amplifier session show <session-id>     # Full details
amplifier session show --transcript     # Show transcript

# Resume sessions
amplifier session resume <session-id>   # Interactive resume
amplifier run --resume <id> "prompt"    # Single-shot resume

# Clean up sessions
amplifier session delete <session-id>   # Delete specific
amplifier session cleanup --days 30     # Delete older than 30 days
amplifier session cleanup --all         # Delete all
```

**Session storage**: `~/.amplifier/projects/<project-slug>/sessions/<session-id>/`

### 3. Profile Commands

**Purpose**: Manage configuration profiles

```bash
# List profiles
amplifier profile list                  # All available
amplifier profile list --verbose        # With details

# Show profile
amplifier profile show <name>           # Basic info
amplifier profile show <name> --detailed  # Full config

# Use profile
amplifier profile use <name>            # Local scope
amplifier profile use <name> --project  # Project default
amplifier profile use <name> --global   # Global default

# Current profile
amplifier profile current               # Show active

# Project default
amplifier profile default               # Show project default
amplifier profile default --set <name>  # Set project default
amplifier profile default --clear       # Clear project default

# Reset
amplifier profile reset                 # Reset local to project default
```

**Related guide**: [profiles.md](./profiles.md)

### 4. Provider Commands

**Purpose**: Manage LLM provider configuration

```bash
# List providers
amplifier provider list                 # All available

# Use provider
amplifier provider use anthropic        # Set provider
amplifier provider use openai --project # Project-level
amplifier provider use azure --global   # Global default

# Current provider
amplifier provider current              # Show active

# Reset
amplifier provider reset                # Reset to project default
amplifier provider reset --scope project # Reset project setting
```

**Supported providers**: anthropic, openai, azure-openai, ollama, mock

### 5. Module Commands

**Purpose**: Manage module sources and discovery

```bash
# List modules
amplifier module list                   # All discovered
amplifier module list --type tool       # Filter by type
amplifier module list --verbose         # With sources

# Show module
amplifier module show <name>            # Module details

# Add/remove sources
amplifier module add <name>             # Add module
amplifier module add <name> --local     # Local scope
amplifier module remove <name>          # Remove module

# Current modules
amplifier module current                # Show active

# Refresh
amplifier module refresh                # Refresh all
amplifier module refresh <name>         # Refresh specific
amplifier module refresh --mutable-only # Only mutable sources
```

**Related guide**: [modules.md](./modules.md)

### 6. Collection Commands

**Purpose**: Manage expertise bundles (profiles + agents + tools)

```bash
# List collections
amplifier collection list               # Installed collections
amplifier collection list --available   # Also show available

# Show collection
amplifier collection show <name>        # Collection details
amplifier collection show <name> --verbose  # With contents

# Add collection
amplifier collection add <git-url>      # Install collection
amplifier collection add <git-url> --local  # Local scope

# Remove collection
amplifier collection remove <name>      # Uninstall
amplifier collection remove <name> --local  # From local

# Refresh
amplifier collection refresh            # Refresh all
amplifier collection refresh <name>     # Refresh specific
amplifier collection refresh --mutable-only  # Only mutable
```

### 7. Source Commands

**Purpose**: Manage module source mappings

```bash
# List sources
amplifier source list                   # All sources
amplifier source list --scope project   # Project sources

# Show source
amplifier source show <id>              # Source details

# Add source
amplifier source add <id> <uri>         # Add mapping
amplifier source add <id> <uri> --local # Local scope

# Remove source
amplifier source remove <id>            # Remove mapping
amplifier source remove <id> --scope project  # From project
```

### 8. Utility Commands

**Purpose**: Setup, updates, and diagnostics

```bash
# First-time setup
amplifier init                          # Interactive setup wizard

# Updates
amplifier update                        # Update everything
amplifier update --check-only           # Check for updates

# Logs
amplifier logs                          # Watch activity log
amplifier logs --follow                 # Continuous follow

# Completion
amplifier --install-completion          # Setup tab completion

# Version
amplifier --version                     # Show version
amplifier --help                        # Show help
```

---

## Session Management

### Session Lifecycle

```
Create Session
    ↓
Execute Prompt(s)
    ↓
Persist State (automatic)
    ↓
[Session can be resumed later]
    ↓
Resume Session
    ↓
Continue Conversation
    ↓
[Optional] Delete Session
```

### Session Storage Structure

```
~/.amplifier/projects/<project-slug>/sessions/<session-id>/
├── transcript.jsonl        # Message history
├── metadata.json           # Session metadata
├── events.jsonl            # Event log
└── state.json              # State checkpoint
```

### Conversational Workflows

**Build context across commands**:

```bash
# Start conversation
$ amplifier run "What files are in this directory?"
Session ID: abc123
[Response listing files]

# Follow-up with context
$ amplifier continue "Show me the largest file"
✓ Resuming session: abc123
  Messages: 2
[Response using context from previous question]

# Continue thread
$ amplifier continue "What's in that file?"
✓ Resuming session: abc123
  Messages: 4
[Response informed by entire conversation]
```

**Unix piping with context**:

```bash
# Initial analysis
$ amplifier run "Analyze this structure"
Session ID: def456
[Analysis]

# Follow-up via pipe
$ cat data.json | amplifier continue
✓ Resuming session: def456
[Analysis of piped data with conversation context]
```

**Resume specific conversation**:

```bash
# List sessions
$ amplifier session list
Recent Sessions:
  abc123  2025-11-17 14:30  6 messages  # File analysis
  def456  2025-11-17 12:15  4 messages  # Data analysis

# Resume specific conversation
$ amplifier run --resume abc123 "What about subdirectories?"
✓ Resuming session: abc123
[Response with full conversation context]
```

### Sub-Session Delegation (Agent Tasks)

When agents use the `task` tool to delegate work:

```python
# Agent delegates to sub-agent
response = await session.execute("Analyze this codebase for bugs")
# Task tool spawns bug-hunter agent as sub-session
# Sub-session has own context, inherits parent config
# Can be resumed by parent for multi-turn collaboration
```

**Key points**:
- Sub-sessions have isolated conversation context
- Inherit parent's modules/config
- Can be resumed for iterative work
- Tracked in session store

See [Agent Delegation docs](../amplifier-app-cli/docs/AGENT_DELEGATION_IMPLEMENTATION.md) for details.

---

## Configuration Management

### Configuration Scopes

Three-tier system for flexible configuration:

```
┌─────────────────────────┐
│  Local Settings         │  .amplifier/settings.local.yaml
│  (not committed)        │  Highest priority
└───────────┬─────────────┘
            │ falls back to
┌───────────▼─────────────┐
│  Project Settings       │  .amplifier/settings.yaml
│  (committed to git)     │  Shared team settings
└───────────┬─────────────┘
            │ falls back to
┌───────────▼─────────────┐
│  Global Settings        │  ~/.amplifier/settings.yaml
│  (user defaults)        │  Personal defaults
└─────────────────────────┘
```

**Use cases**:
- **Local**: Personal overrides (API keys, models)
- **Project**: Team defaults (profile, modules)
- **Global**: User defaults across all projects

### Configuration Files

**Project settings** (`.amplifier/settings.yaml`):
```yaml
profile: developer-expertise:dev
provider: anthropic
sources:
  tool-custom: git+https://github.com/org/tool-custom@main
```

**Local settings** (`.amplifier/settings.local.yaml`):
```yaml
profile: custom-dev  # Override for just you
provider: openai     # Use different provider
```

**Global settings** (`~/.amplifier/settings.yaml`):
```yaml
profile: foundation:base
provider: anthropic
```

### Command Scope Flags

Most configuration commands support scope flags:

```bash
# Local scope (default)
amplifier profile use dev

# Project scope (committed)
amplifier profile use dev --project

# Global scope (user default)
amplifier profile use dev --global
```

---

## Interactive Mode

### Starting Interactive Mode

```bash
# Default profile
amplifier

# Specific profile
amplifier --profile full

# Explicit chat mode
amplifier --mode chat
```

### Slash Commands

Interactive mode supports slash commands for session control:

| Command | Purpose | Example |
|---------|---------|---------|
| `/help` | Show help | `/help` |
| `/status` | Session info | `/status` |
| `/tools` | List tools | `/tools` |
| `/profile` | Current profile | `/profile` |
| `/think` | Enable plan mode | `/think` |
| `/exit` | Exit session | `/exit` or `Ctrl+D` |

### Interactive Features

**Tab completion**: Commands, profiles, modules auto-complete

**Multi-line input**: Use `\` for line continuation:
```
> This is a long \
... prompt that spans \
... multiple lines
```

**History**: Up/down arrows for command history

**Context persistence**: All messages saved to session

---

## Output Formats

### Text Output (Default)

Standard human-readable output:

```bash
$ amplifier run "What is 2+2?"
The answer is 4.
```

### JSON Output

Structured output for automation:

```bash
$ amplifier run --output-format json "What is 2+2?"
{
  "status": "success",
  "response": "The answer is 4.",
  "session_id": "abc123",
  "profile": "developer-expertise:dev",
  "model": "anthropic/claude-sonnet-4-5",
  "timestamp": "2025-11-17T14:30:00Z"
}
```

**Error format**:
```json
{
  "status": "error",
  "error": "Provider not configured",
  "session_id": null,
  "profile": null,
  "model": null,
  "timestamp": "2025-11-17T14:30:00Z"
}
```

### Output Streams

- **stdout**: Main output (response or JSON)
- **stderr**: Diagnostics, progress, hook output

**Clean JSON** (suppress diagnostics):
```bash
amplifier run --output-format json "prompt" 2>/dev/null | python process.py
```

**Capture both**:
```bash
amplifier run --output-format json "prompt" 1>response.json 2>diagnostics.log
```

See [OUTPUT_FORMATS.md](../amplifier-app-cli/docs/OUTPUT_FORMATS.md) for complete details.

---

## Development Patterns

### Local Testing During Development

When working in `amplifier-dev`:

```bash
# Local packages already installed (see scripts/install-dev.sh)
# Local source overrides configured (see .amplifier/settings.yaml)

# Test immediately after changes
amplifier run "test prompt"

# Interactive testing
amplifier
```

**Why this works**:
- `.amplifier/settings.yaml` maps module names to local directories
- Editable installs reflect changes immediately
- No reinstall needed for Python code changes

### Shell Completion Setup

One-command installation:

```bash
amplifier --install-completion
```

**What happens**:
1. Detects shell (bash, zsh, fish)
2. Appends completion line to config file
3. Safe to run multiple times

**Manual activation**:
```bash
source ~/.bashrc   # bash
source ~/.zshrc    # zsh
# Or start new terminal
```

### Accessing Session Logs

**Session logs** location:
```
~/.amplifier/projects/<project-slug>/sessions/<session-id>/events.jsonl
```

**Find recent logs**:
```bash
# Most recent session
ls -lt ~/.amplifier/projects/*/sessions/*/events.jsonl | head -1

# Recent sessions for current project
ls -lt ~/.amplifier/projects/<project-slug>/sessions/*/events.jsonl | head -5
```

**Search logs**:
```bash
# Find specific events
grep '"event":\s*"llm:request:raw"' <log-file>

# Pretty-print event
grep '"event":\s*"llm:response:raw"' <log-file> | head -1 | python3 -m json.tool
```

**Debug logging levels**:
- Standard debug: `llm:request:debug`, `llm:response:debug` (summaries)
- Raw debug: `llm:request:raw`, `llm:response:raw` (complete API I/O)

Enable in profile config:
```yaml
providers:
  - module: provider-anthropic
    config:
      debug: true       # Standard debug
      raw_debug: true   # Raw debug (requires debug: true)
```

---

## Troubleshooting

### Issue: Command Not Found

**Error**: `amplifier: command not found`

**Check**:
1. Amplifier installed: `uv tool list | grep amplifier`
2. Shell PATH includes `~/.local/bin`
3. Fresh shell after installation

**Solution**:
```bash
# Install
uv tool install git+https://github.com/microsoft/amplifier@next

# Verify PATH
echo $PATH | grep ".local/bin"

# Add to PATH if missing (bash)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Issue: Profile Not Found

**Error**: `Profile 'xyz' not found`

**Check**:
1. Profile exists: `amplifier profile list`
2. Correct name/collection reference
3. Collection installed: `amplifier collection list`

**Solution**:
```bash
# List available
amplifier profile list

# Check specific profile
amplifier profile show xyz

# Install collection if needed
amplifier collection add <collection-url>
```

### Issue: Provider Not Configured

**Error**: `No provider configured` or `API key not set`

**Check**:
1. Provider set: `amplifier provider current`
2. API key in env or config
3. Profile includes provider

**Solution**:
```bash
# Run setup wizard
amplifier init

# Or set manually
amplifier provider use anthropic
export ANTHROPIC_API_KEY="your-key"
```

### Issue: Module Not Loading

**Error**: `Failed to load module 'tool-xyz'`

**Check**:
1. Module available: `amplifier module list`
2. Source configured: `amplifier source list`
3. Profile includes module

**Solution**:
```bash
# Check module
amplifier module show tool-xyz

# Add source if missing
amplifier source add tool-xyz git+https://github.com/org/tool-xyz@main

# Refresh
amplifier module refresh
```

### Issue: Session Not Resuming

**Error**: `Session 'abc123' not found` or resume fails

**Check**:
1. Session exists: `amplifier session list`
2. Session ID correct
3. Session directory exists

**Solution**:
```bash
# List sessions
amplifier session list

# Check session details
amplifier session show <session-id>

# Verify storage
ls ~/.amplifier/projects/*/sessions/<session-id>/
```

### Issue: JSON Output Invalid

**Problem**: JSON output mixed with diagnostics

**Solution**: Redirect stderr to suppress diagnostics:
```bash
amplifier run --output-format json "prompt" 2>/dev/null
```

Or capture separately:
```bash
amplifier run --output-format json "prompt" 1>out.json 2>diag.log
```

---

## Logging and Inspection

Understanding where Amplifier creates files and how to inspect system state is crucial for debugging and monitoring.

### Directory Structure

**Amplifier creates a hierarchical directory structure**:

```
~/.amplifier/                                    # User-level amplifier data
├── settings.yaml                                # Global user settings
├── profiles/                                    # Custom user profiles (if any)
├── collections/                                 # Installed collections
└── projects/                                    # Per-project data
    └── <project-slug>/                          # Project directory (based on cwd)
        ├── settings.yaml                        # Project-level settings
        ├── sessions/                            # Session data
        │   └── <session-id>/                    # Individual session
        │       ├── events.jsonl                 # Event log (JSONL format)
        │       ├── context.json                 # Session context/state
        │       └── metadata.json                # Session metadata
        └── cache/                               # Cached data (if applicable)

.amplifier/                                      # Local project directory
├── settings.yaml                                # Project settings (committed)
└── settings.local.yaml                          # Local overrides (gitignored)
```

### Project Slug Generation

The **project slug** is derived from the current working directory:

```bash
# Working directory: /home/user/repos/my-project
# Project slug: -home-user-repos-my-project

# Example paths:
# Session: ~/.amplifier/projects/-home-user-repos-my-project/sessions/<id>/
# Events: ~/.amplifier/projects/-home-user-repos-my-project/sessions/<id>/events.jsonl
```

**Finding your project slug**:

```bash
# Current directory path
pwd
# Output: /home/user/repos/my-project

# Project slug is path with slashes replaced by dashes, prefixed with dash
# Result: -home-user-repos-my-project
```

### Session Storage

**Each session creates a directory** containing all session data:

```
~/.amplifier/projects/<project-slug>/sessions/<session-id>/
├── events.jsonl      # Complete event log (append-only)
├── context.json      # Session context and message history
└── metadata.json     # Session metadata (profile, model, timestamps)
```

**Finding session directories**:

```bash
# List all sessions for current project
ls -lt ~/.amplifier/projects/*/sessions/

# Find most recent session
ls -lt ~/.amplifier/projects/*/sessions/ | head -1

# Find sessions from today
find ~/.amplifier/projects/*/sessions/ -type d -name "*" -mtime -1
```

**Inspecting session data**:

```bash
# View session metadata
cat ~/.amplifier/projects/<slug>/sessions/<id>/metadata.json | jq .

# View context/messages
cat ~/.amplifier/projects/<slug>/sessions/<id>/context.json | jq .

# View event log
cat ~/.amplifier/projects/<slug>/sessions/<id>/events.jsonl | head -10
```

### Event Logs

**Event logs** are append-only JSONL files containing all session events:

```jsonl
{"ts":"2025-01-17T10:30:00Z","lvl":"info","event":"session:start","data":{...}}
{"ts":"2025-01-17T10:30:01Z","lvl":"info","event":"provider:request","data":{...}}
{"ts":"2025-01-17T10:30:03Z","lvl":"info","event":"provider:response","data":{...}}
{"ts":"2025-01-17T10:30:03Z","lvl":"info","event":"session:end","data":{...}}
```

**Event log location**:

```
~/.amplifier/projects/<project-slug>/sessions/<session-id>/events.jsonl
```

**Reading event logs**:

```bash
# View all events
cat events.jsonl | jq .

# Filter by event type
grep '"event":"provider:request"' events.jsonl | jq .

# Filter by timestamp
grep '"ts":"2025-01-17T10:3' events.jsonl | jq .

# Count events by type
cat events.jsonl | jq -r .event | sort | uniq -c

# Extract provider requests only
grep '"event":"provider:request"' events.jsonl | jq .data
```

**Common event types**:

| Event | When | Contains |
|-------|------|----------|
| `session:start` | Session begins | Mount plan, profile, session_id |
| `session:end` | Session completes | Duration, final state |
| `prompt:submit` | User submits prompt | Prompt text, user context |
| `prompt:complete` | Response generated | Response text, token usage |
| `provider:request` | LLM API call starts | Messages, model, config |
| `provider:response` | LLM API responds | Response, usage, latency |
| `tool:pre` | Before tool execution | Tool name, input |
| `tool:post` | After tool execution | Tool name, result |
| `context:pre_compact` | Before compaction | Message count, token count |
| `context:post_compact` | After compaction | New message count, removed count |

### Debug Logging

**Enable detailed logging** to capture more information:

**In profiles** (persistent):

```yaml
# profiles/debug.md
---
extends: dev
---

# Debug Profile

Enable detailed logging for troubleshooting.

```yaml
hooks:
  - module: hooks-logging
    source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
    config:
      debug: true           # Emits llm:request:debug, llm:response:debug
      raw_debug: true       # Emits llm:request:raw, llm:response:raw (full API I/O)
```
```

**What debug levels provide**:

| Level | Events | Content |
|-------|--------|---------|
| **Standard** | `provider:request`, `provider:response` | Basic request/response info |
| **Debug** (`debug: true`) | + `llm:request:debug`, `llm:response:debug` | Request/response summaries |
| **Raw Debug** (`raw_debug: true`) | + `llm:request:raw`, `llm:response:raw` | Complete API payloads |

**Viewing debug events**:

```bash
# View request summaries
grep '"event":"llm:request:debug"' events.jsonl | jq .

# View full request payload
grep '"event":"llm:request:raw"' events.jsonl | jq .data

# View full response payload
grep '"event":"llm:response:raw"' events.jsonl | jq .data

# Pretty-print single event
grep '"event":"llm:response:raw"' events.jsonl | head -1 | jq .
```

### Configuration Files

**Three-tier configuration system**:

```
1. Local Settings (.amplifier/settings.local.yaml)
   ↓ overrides
2. Project Settings (.amplifier/settings.yaml)
   ↓ overrides
3. Global Settings (~/.amplifier/settings.yaml)
   ↓ falls back to
4. System Defaults (hardcoded)
```

**Configuration file locations**:

| Scope | Path | Purpose | Git Status |
|-------|------|---------|-----------|
| **Local** | `.amplifier/settings.local.yaml` | Developer overrides | Gitignored |
| **Project** | `.amplifier/settings.yaml` | Team configuration | Committed |
| **Global** | `~/.amplifier/settings.yaml` | User defaults | User-specific |

**Inspecting configuration**:

```bash
# View effective configuration (merged from all layers)
amplifier config show

# View specific layer
cat ~/.amplifier/settings.yaml                  # Global
cat .amplifier/settings.yaml                    # Project
cat .amplifier/settings.local.yaml              # Local

# View with jq for readability
cat ~/.amplifier/settings.yaml | yq -o json | jq .
```

**Common configuration locations**:

```yaml
# ~/.amplifier/settings.yaml
default_profile: dev

profiles:
  search_paths:
    - ~/.amplifier/profiles
    - ~/custom-profiles

sources:
  provider-anthropic: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
  tool-custom: file:///home/user/custom-tools/amplifier-module-tool-custom

collections:
  - name: toolkit
    source: git+https://github.com/microsoft/amplifier-collection-toolkit@main
```

### Module Installation

**Modules are installed on-demand** to a uv cache:

```
~/.cache/uv/                                     # uv cache directory
└── ... (managed by uv, typically not inspected)
```

**Checking installed modules**:

```bash
# List all installed amplifier modules
uv pip list | grep amplifier

# Check specific module
uv pip show amplifier-module-provider-anthropic

# Show installation location
uv pip show amplifier-module-provider-anthropic | grep Location
```

**Module source resolution**:

```bash
# List configured sources
amplifier source list

# Add custom source
amplifier source add tool-custom file:///path/to/module

# Remove source
amplifier source remove tool-custom
```

### Collection Installation

**Collections are installed** to a dedicated directory:

```
~/.amplifier/collections/<collection-name>/
├── agents/              # Agent definitions
├── scenario-tools/      # CLI tools
├── docs/                # Documentation
└── pyproject.toml       # Collection metadata
```

**Checking installed collections**:

```bash
# List installed collections
amplifier collection list

# Show collection details
amplifier collection show toolkit

# View collection directory
ls ~/.amplifier/collections/amplifier-collection-toolkit/
```

### Finding Recent Activity

**Find most recent session**:

```bash
# Most recent session directory
ls -lt ~/.amplifier/projects/*/sessions/ | head -1

# Most recent event log
ls -lt ~/.amplifier/projects/*/sessions/*/events.jsonl | head -1

# Tail recent events
tail -f $(ls -t ~/.amplifier/projects/*/sessions/*/events.jsonl | head -1)
```

**View recent sessions**:

```bash
# List recent sessions (5 most recent)
amplifier session list --limit 5

# Show specific session
amplifier session show <session-id>

# View session events
cat ~/.amplifier/projects/<slug>/sessions/<id>/events.jsonl | jq .
```

### Cleanup

**Sessions accumulate over time**. Clean up old sessions to save disk space:

```bash
# Remove sessions older than 30 days
amplifier session cleanup --days 30

# Dry run (show what would be deleted)
amplifier session cleanup --days 30 --dry-run

# Manual cleanup (if needed)
rm -rf ~/.amplifier/projects/*/sessions/<old-session-id>
```

**Configuration cleanup**:

```bash
# Remove custom profile
rm ~/.amplifier/profiles/my-profile.md

# Remove local settings
rm .amplifier/settings.local.yaml

# Reset to defaults
rm ~/.amplifier/settings.yaml
```

### Monitoring Active Sessions

**During execution**, monitor session activity:

```bash
# Get session ID from amplifier run
SESSION_ID=$(amplifier run "test" 2>&1 | grep -oP 'session_id: \K[a-f0-9-]+')

# Tail event log in real-time
tail -f ~/.amplifier/projects/*/sessions/$SESSION_ID/events.jsonl | jq .

# Watch for specific events
tail -f ~/.amplifier/projects/*/sessions/$SESSION_ID/events.jsonl | grep provider:request
```

### Troubleshooting with Logs

**Common debugging workflows**:

**1. Find why a command failed**:

```bash
# Get last session ID
LAST_SESSION=$(ls -t ~/.amplifier/projects/*/sessions/ | head -1 | xargs basename)

# View error events
grep '"lvl":"error"' ~/.amplifier/projects/*/sessions/$LAST_SESSION/events.jsonl | jq .

# View full log around error
cat ~/.amplifier/projects/*/sessions/$LAST_SESSION/events.jsonl | jq .
```

**2. Understand token usage**:

```bash
# Extract token usage from provider responses
grep '"event":"provider:response"' events.jsonl | jq '.data.usage'

# Sum total tokens
grep '"event":"provider:response"' events.jsonl | jq '.data.usage.total_tokens' | awk '{sum+=$1} END {print sum}'
```

**3. See what tools were called**:

```bash
# List all tool executions
grep '"event":"tool:pre"' events.jsonl | jq '.data.tool'

# Count tool usage
grep '"event":"tool:pre"' events.jsonl | jq -r '.data.tool' | sort | uniq -c
```

**4. Track session duration**:

```bash
# Get start and end times
START=$(grep '"event":"session:start"' events.jsonl | jq -r .ts)
END=$(grep '"event":"session:end"' events.jsonl | jq -r .ts)

echo "Start: $START"
echo "End: $END"
```

### Summary

**Key locations to remember**:

| What | Where |
|------|-------|
| **Global settings** | `~/.amplifier/settings.yaml` |
| **Project settings** | `.amplifier/settings.yaml` |
| **Session data** | `~/.amplifier/projects/<slug>/sessions/<id>/` |
| **Event logs** | `~/.amplifier/projects/<slug>/sessions/<id>/events.jsonl` |
| **Collections** | `~/.amplifier/collections/<name>/` |
| **Custom profiles** | `~/.amplifier/profiles/` |

**Quick inspection commands**:

```bash
# Where am I?
pwd

# What's my project slug?
# (Replace / with - and prefix with -)

# Find recent sessions
ls -lt ~/.amplifier/projects/*/sessions/ | head -5

# View last session events
cat $(ls -t ~/.amplifier/projects/*/sessions/*/events.jsonl | head -1) | jq .

# Check configuration
amplifier config show

# List installed modules
uv pip list | grep amplifier
```

---

## Reference

### File Locations

| Purpose | Path |
|---------|------|
| CLI implementation | `amplifier-app-cli/amplifier_app_cli/` |
| Bundled profiles | `amplifier-app-cli/data/profiles/` |
| Bundled collections | `amplifier-app-cli/data/collections/` |
| Session storage | `~/.amplifier/projects/<project-slug>/sessions/` |
| Global settings | `~/.amplifier/settings.yaml` |
| Project settings | `.amplifier/settings.yaml` |
| Local settings | `.amplifier/settings.local.yaml` |

### Key Implementation Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point |
| `commands/profile.py` | Profile commands |
| `commands/session.py` | Session commands |
| `commands/provider.py` | Provider commands |
| `commands/module.py` | Module commands |
| `commands/collection.py` | Collection commands |
| `session_store.py` | Session persistence |
| `session_spawner.py` | Agent delegation |
| `lib/mention_loading/` | @mention expansion |

### Documentation

| Document | Purpose |
|----------|---------|
| `docs/AGENT_DELEGATION_IMPLEMENTATION.md` | Sub-session spawning |
| `docs/CONTEXT_LOADING.md` | @mention system |
| `docs/INTERACTIVE_MODE.md` | REPL and slash commands |
| `docs/OUTPUT_FORMATS.md` | JSON output details |
| `docs/decisions/` | Architectural decisions |

### Related Guides

- [**Profiles Guide**](./profiles.md) - Configuration profiles
- [**Modules Guide**](./modules.md) - Module system
- [**Mounts Guide**](./mounts.md) - Mount plans
- [**Development Guide**](./development.md) - Development workflows and custom modules

---

## Quick Reference

### Common Workflows

```bash
# First-time setup
amplifier init

# Single command
amplifier run "Your prompt"

# Interactive mode
amplifier

# Resume conversation
amplifier continue "Follow-up question"

# Use specific profile
amplifier run --profile full "Your prompt"

# JSON output
amplifier run --output-format json "Your prompt"

# List sessions
amplifier session list

# Clean up old sessions
amplifier session cleanup --days 30
```

### Configuration Hierarchy

```
Local Settings (.amplifier/settings.local.yaml)
    ↓ overrides
Project Settings (.amplifier/settings.yaml)
    ↓ overrides
Global Settings (~/.amplifier/settings.yaml)
    ↓ falls back to
System Defaults
```

### Scope Flags

```bash
# Local (default)
amplifier <command> <args>

# Project (committed)
amplifier <command> <args> --project

# Global (user default)
amplifier <command> <args> --global
```

---

**For more information**, see the [Amplifier User Guide](../amplifier/docs/USER_ONBOARDING.md).
