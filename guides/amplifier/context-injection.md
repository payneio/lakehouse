# Context Injection Architecture

**How context flows from profiles → @mentions → messages → provider API**

---

## Overview

Context injection loads and structures content from multiple sources into LLM-compatible message formats:

- **Profile @mentions** → Prepended to system instruction
- **Runtime @mentions** → Developer messages before user input
- **Context managers** → Store/retrieve conversation history
- **Provider adapters** → Transform messages per API requirements

**Related docs**: [@CONTEXT_LOADING.md](../amplifier-app-cli/docs/CONTEXT_LOADING.md) (detailed @mention mechanics)

---

## Table of Contents

1. [Context Sources](#1-context-sources)
2. [Context Flow](#2-context-flow)
3. [Message Roles](#3-message-roles)
4. [Collection-Based @Mentions](#4-collection-based-mentions)
5. [Architecture](#5-architecture)
6. [Provider Transformations](#6-provider-transformations)
7. [Implementation Details](#7-implementation-details)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Context Sources

### Profile Markdown
Profile body (below YAML frontmatter) becomes the base system instruction.

```markdown
# ~/.amplifier/profiles/dev.md
---
profile:
  name: dev
---

You are an Amplifier development assistant.
Follow conventions in @AGENTS.md and @DISCOVERIES.md.
```

### Profile @Mentions
@mentions in profile markdown are resolved and **prepended** to the profile body:

```
System = [AGENTS.md content] + [DISCOVERIES.md content] + [Profile body]
```

**Processing**: `_process_profile_mentions()` in `main.py`

### Runtime @Mentions
@mentions in user input become **developer messages** inserted before the user message:

```python
# User input: "Explain @FILE.md"
# Results in:
[Developer] "<context_file>FILE.md content</context_file>"
[User]      "Explain @FILE.md"
```

**Processing**: `_process_runtime_mentions()` in `main.py`

### Context Managers
Modules that store conversation history (session memory):

```python
context = session.coordinator.get("context")

await context.add_message(message)        # Store
messages = await context.get_messages()   # Retrieve
await context.compact()                   # Reduce size
```

**Implementations**: `context-simple` (in-memory), `context-persistent` (file-based)

---

## 2. Context Flow

### High-Level Pipeline

```
Profile.md (YAML + markdown + @mentions)
    ↓
ProfileLoader → parse YAML + markdown
    ↓
MentionLoader → detect @mentions
    ↓
MentionResolver → resolve to file paths
    ↓
ContentDeduplicator → ensure unique content
    ↓
prepend_context_to_markdown() → combine
    ↓
AmplifierSession → initialize
    ↓
context.add_message(role="system") → store
    ↓
[Runtime @mentions processed similarly → role="developer"]
    ↓
Orchestrator → execute
    ↓
Provider → transform & submit to API
```

### Key Stages

**1. Profile Loading**
```python
profile_file = profile_loader.find_profile_file(profile_name)
markdown_body = parse_markdown_body(profile_file.read_text())
```

**2. @Mention Resolution & Loading**
```python
loader = MentionLoader()
deduplicator = session.coordinator.get_capability("mention_deduplicator")
context_messages = loader.load_mentions(
    markdown_body,
    relative_to=profile_file.parent,
    deduplicator=deduplicator
)
```

**3. Content Prepending**
```python
context_content = "\n\n".join([msg.content for msg in context_messages])
markdown_body = f"{context_content}\n\n{markdown_body}"
```

**4. System Message Storage**
```python
context = session.coordinator.get("context")
await context.add_message({"role": "system", "content": markdown_body})
```

**5. Runtime Processing** (per user turn)
```python
# If user input has @mentions:
if has_mentions(prompt):
    context_msgs = loader.load_mentions(prompt, relative_to=Path.cwd())
    for msg in context_msgs:
        await context.add_message(msg.model_dump())  # Developer messages
await context.add_message({"role": "user", "content": prompt})
```

**6. Provider Submission**
```python
messages = await context.get_messages()
response = await provider.complete(messages)  # Transforms per API
```

---

## 3. Message Roles

| Role | Source | Created | Compacted? | Purpose |
|------|--------|---------|------------|---------|
| `system` | Profile markdown + @mentions | Session init | Never | Agent identity & instructions |
| `developer` | Runtime @mentions | Before user msg | Yes | External file content |
| `user` | User input | Each turn | Yes | User's request |
| `assistant` | LLM response | After completion | Yes | Agent's response |

### System Messages
- **Content**: Profile body with @mentions prepended
- **Created**: `_process_profile_mentions()` during session init
- **Never compacted**: Always preserved
- **Single instance**: One per session

### Developer Messages
- **Content**: Runtime @mention file content wrapped in `<context_file>` tags
- **Created**: `_process_runtime_mentions()` when user input has @mentions
- **Inserted before**: Corresponding user message
- **Provider transform**: Becomes `role="user"` (Anthropic) or prepended to input (OpenAI)

### User/Assistant Messages
Standard conversation turns, subject to compaction strategies.

---

## 4. Collection-Based @Mentions

### Syntax
`@collection:resource/path` - References from registered collections

### Examples
```markdown
# Bundled collections
@foundation:context/IMPLEMENTATION_PHILOSOPHY.md
@foundation:profiles/base.md

# User collections (~/.amplifier/collections/)
@my-company:standards/coding-guidelines.md

# Project collections (.amplifier/collections/)
@project:docs/API_STANDARDS.md
```

### Search Precedence
1. **Project**: `.amplifier/collections/collection/`
2. **User**: `~/.amplifier/collections/collection/`
3. **Bundled**: Package collections (e.g., `foundation`)

**Example resolution**:
```
@foundation:context/AGENTS.md
  → Check .amplifier/collections/foundation/context/AGENTS.md
  → Check ~/.amplifier/collections/foundation/context/AGENTS.md
  → Check [bundled]/foundation/context/AGENTS.md ✓
```

This allows projects to override bundled resources.

### Special Prefixes
- `@user:path` → Force `~/.amplifier/path`
- `@project:path` → Force `.amplifier/path`
- `@~/path` → Expand from home directory

### Standard Collections

**foundation** (bundled):
- AGENTS.md, DISCOVERIES.md
- Base profiles
- Implementation philosophy

**developer-expertise** (optional):
- Language/framework patterns
- Install: `amplifier collection install developer-expertise`

### Profile Usage
```yaml
---
profile:
  name: backend-dev
  extends: foundation:profiles/base.md
---

Context from collections:
- @foundation:context/IMPLEMENTATION_PHILOSOPHY.md
- @developer-expertise:python/best-practices.md
- @my-company:standards/api-design.md
```

---

## 5. Architecture

### Component Diagram

```
┌─────────────────────────────────────┐
│   AmplifierSession (Kernel)         │
│   - Coordinator                     │
│   - Module mounting                 │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┬─────────────┐
    ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│Context  │  │Orchestr.│  │Provider │
│Manager  │  │         │  │         │
└─────────┘  └─────────┘  └─────────┘
    ▲                          ▲
    │                          │
┌───┴──────────────────────────┴────┐
│ App Layer (amplifier-app-cli)     │
│ - MentionLoader                    │
│ - MentionResolver                  │
│ - ContentDeduplicator              │
│ - ProfileLoader                    │
└────────────────────────────────────┘
```

### Layer Boundaries

**Kernel (amplifier-core)**:
- Session lifecycle, module coordination
- Does NOT handle: file I/O, @mention resolution, profile parsing

**App (amplifier-app-cli)**:
- Profile loading, @mention file I/O, path resolution
- Policy: when to process @mentions, where to search

**Modules**:
- Context storage, orchestration loops, provider adapters
- Pluggable via entry points

### Capabilities
App layer registers capabilities modules can use:

```python
# App layer:
session.coordinator.register_capability("mention_resolver", MentionResolver())
session.coordinator.register_capability("mention_deduplicator", ContentDeduplicator())

# Module usage:
resolver = coordinator.get_capability("mention_resolver")
path = resolver.resolve("@AGENTS.md")
```

---

## 6. Provider Transformations

Internal message format transforms per provider API requirements.

### Anthropic Messages API

**Internal → Anthropic**:
```python
# Internal messages:
[
  {"role": "system", "content": "You are..."},
  {"role": "developer", "content": "<context_file>...</context_file>"},
  {"role": "user", "content": "Explain @FILE.md"}
]

# Anthropic API call:
{
  "model": "claude-3-5-sonnet-20241022",
  "system": "You are...",  # system extracted to parameter
  "messages": [
    {"role": "user", "content": "<context_file>...</context_file>"},  # developer → user
    {"role": "user", "content": "Explain @FILE.md"}
  ]
}
```

### OpenAI/Azure Responses API

**Internal → OpenAI**:
```python
# Internal messages:
[
  {"role": "system", "content": "You are..."},
  {"role": "developer", "content": "<context_file>...</context_file>"},
  {"role": "user", "content": "Explain @FILE.md"}
]

# OpenAI API call:
{
  "model": "gpt-4",
  "instructions": "You are...",  # system extracted
  "input": "<context_file>...</context_file>\n\nUser: Explain @FILE.md"  # developer + user combined
}
```

### Role Mapping

| Internal | Anthropic | OpenAI |
|----------|-----------|--------|
| `system` | `system` param | `instructions` param |
| `developer` | `role="user"` msg | Prepended to input |
| `user` | `role="user"` msg | Part of input string |
| `assistant` | `role="assistant"` msg | Conversation history |

---

## 7. Implementation Details

### Profile Processing

**Function**: `_process_profile_mentions()` in `amplifier-app-cli/amplifier_app_cli/main.py`

```python
async def _process_profile_mentions(session: AmplifierSession, profile_name: str) -> None:
    # 1. Load profile
    profile_loader = create_profile_loader()
    profile_file = profile_loader.find_profile_file(profile_name)
    markdown_body = parse_markdown_body(profile_file.read_text())

    # 2. Check for @mentions
    if not has_mentions(markdown_body):
        return

    # 3. Load @mentioned files
    loader = MentionLoader()
    deduplicator = session.coordinator.get_capability("mention_deduplicator")
    context_messages = loader.load_mentions(
        markdown_body,
        relative_to=profile_file.parent,
        deduplicator=deduplicator
    )

    # 4. Prepend to markdown
    markdown_body = prepend_context_to_markdown(context_messages, markdown_body)

    # 5. Store as system message
    context = session.coordinator.get("context")
    await context.add_message({"role": "system", "content": markdown_body})
```

### Runtime Processing

**Function**: `_process_runtime_mentions()` in `amplifier-app-cli/amplifier_app_cli/main.py`

```python
async def _process_runtime_mentions(session: AmplifierSession, prompt: str) -> None:
    if not has_mentions(prompt):
        return

    loader = MentionLoader()
    deduplicator = session.coordinator.get_capability("mention_deduplicator")
    context_messages = loader.load_mentions(
        prompt,
        relative_to=Path.cwd(),
        deduplicator=deduplicator
    )

    context = session.coordinator.get("context")
    for msg in context_messages:
        await context.add_message(msg.model_dump())  # Add before user message
```

### Content Deduplication

**Session-wide deduplication** via hash-based tracking:

```python
class ContentDeduplicator:
    def __init__(self):
        self._seen_hashes: set[str] = set()
        self._content_map: dict[str, ContextFile] = {}

    def add_file(self, path: Path, content: str) -> bool:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if content_hash in self._seen_hashes:
            # Already seen - add path to existing entry
            self._content_map[content_hash].paths.append(path)
            return False  # Not unique

        self._seen_hashes.add(content_hash)
        self._content_map[content_hash] = ContextFile(paths=[path], content=content)
        return True  # Unique
```

Files with identical content are loaded once, all paths credited in `<context_file paths="...">`.

### Context Manager Compaction

**Simple strategy** (context-simple):
```python
async def compact(self) -> int:
    # Keep system + last N messages + all tool pairs
    system_msgs = [m for m in self.messages if m["role"] == "system"]
    recent_msgs = self.messages[-20:]  # Last 10 turns (user+assistant)
    tool_pairs = self._extract_tool_pairs(self.messages)

    compacted = system_msgs + tool_pairs + recent_msgs
    tokens_saved = self.token_count - self._count_tokens(compacted)
    self.messages = compacted
    return tokens_saved
```

**Smart strategy** (context-persistent):
- Semantic importance scoring
- Recency weighting
- User-defined retention rules

---

## 8. Troubleshooting

### Context Not Loading

**Check profile has markdown body**:
```bash
amplifier profile show PROFILE_NAME
```

**Verify @mention resolves**:
```bash
# Check file exists in search paths:
ls .amplifier/context/FILE.md
ls ~/.amplifier/context/FILE.md
```

**Check logs**:
```bash
amplifier logs | grep -i "mention\|context"
```

Look for: `"Processing @mentions"`, `"Loaded N files"`, `"Adding system instruction"`

### Duplicate Content

**Expected**: ContentDeduplicator prevents duplicates. Same file loaded once, all @mention paths credited.

**Check if actually duplicate**:
- Profile @mentions → System message (prepended)
- Runtime @mentions → Developer messages (separate)
- Different roles = both valid, not duplicates

**Compare files**:
```bash
diff file1.md file2.md  # Even slight differences = different hash
```

### Missing Context

**Verify @mention syntax**:
- ✓ `@FILE.md`
- ✗ `@ FILE.md` (space)
- ✗ `@FILE` (no extension)

**Check search paths**:
MentionResolver searches:
1. Current working directory
2. `.amplifier/context/`
3. `~/.amplifier/context/`
4. Bundled context

**Check logs for skips**:
```bash
amplifier logs | grep -i "skip\|not found"
```

Files silently skip if not found (no error raised).

### Performance Issues

**Check token usage**:
```python
token_count = await context.get_token_count()
print(f"Context tokens: {token_count}")
```

**Profile excessive @mentions**:
- Each @mention loads entire file
- Large files = large context
- Split large context files

**Lower compaction threshold**:
```yaml
context:
  config:
    compact_threshold: 0.85  # Compact earlier
```

### Inspect Message Stack

```bash
amplifier logs --session SESSION_ID | grep "provider:request"
```

Verify:
1. System message includes prepended @mentions
2. Developer messages before user messages
3. Messages in correct order (system, developer, user, assistant)
4. No tool-use without matching tool-result

---

## Appendices

### Key Code Locations

**Profile loading**:
- `amplifier-profiles`: `parse_markdown_body()`

**@mention loading**:
- `amplifier-app-cli/amplifier_app_cli/lib/mention_loading/`
  - `MentionLoader`, `MentionResolver`, `ContentDeduplicator`

**Context injection**:
- `amplifier-app-cli/amplifier_app_cli/main.py`
  - `_process_profile_mentions()`, `_process_runtime_mentions()`
- `amplifier-app-cli/amplifier_app_cli/lib/mention_loading/loader.py`
  - `prepend_context_to_markdown()`

**Context managers**:
- `amplifier-module-context-simple/`
- `amplifier-module-context-persistent/`

### Related Documentation

- **[@CONTEXT_LOADING.md](../amplifier-app-cli/docs/CONTEXT_LOADING.md)** - @mention mechanics
- **[@guides/context.md](context.md)** - Context manager user guide
- **[Profile Authoring](https://github.com/microsoft/amplifier-profiles)** - Creating profiles
- **[Collections Guide](https://github.com/microsoft/amplifier-collections)** - Collection system

### Glossary

**@mention**: Syntax for file references (`@FILE.md`), auto-resolved and loaded

**MentionLoader**: Loads @mentioned files recursively

**ContentDeduplicator**: Hash-based dedup, one copy per unique content

**Context Manager**: Session memory module (add/get messages, compact)

**Message Stack**: Ordered conversation messages from `context.get_messages()`

**Prepending**: Adding @mention content before profile markdown in system instruction

**Compaction**: Reducing context size by removing messages while preserving critical content

**Tool Pair**: Atomic `tool_use` + `tool_result` that must stay together

---

## Summary

Context injection pipeline:

1. **Profile loading** → Parse YAML + markdown
2. **@mention resolution** → Locate files in search paths
3. **Content loading** → Read files, follow nested @mentions
4. **Deduplication** → Hash-based, load once per unique content
5. **Prepending** → Profile @mentions prepended to system message
6. **System instruction** → Enhanced markdown stored as `role="system"`
7. **Runtime @mentions** → User input @mentions become `role="developer"` messages
8. **Message stack** → Context manager maintains ordered list
9. **Provider transform** → Adapt to API-specific format
10. **API submission** → Send to LLM

**Key principles**:
- Profile @mentions → Prepended to system
- Runtime @mentions → Developer messages before user
- ContentDeduplicator → Session-wide, prevents reloading
- Context managers → Store, compact, retrieve
- Provider modules → Transform per API

Understanding this flow enables effective profile authoring, context debugging, and usage optimization.
