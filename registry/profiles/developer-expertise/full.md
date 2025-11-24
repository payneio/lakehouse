---
profile:
  name: full
  version: 1.0.0
  description: Full configuration with all available tools, hooks, and agents
session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/microsoft/amplifier-module-loop-streaming@main
    config:
      extended_thinking: true
  context:
    module: context-persistent
    source: git+https://github.com/microsoft/amplifier-module-context-persistent@main
    config:
      max_tokens: 200000
      compact_threshold: 0.9
      auto_compact: true
  injection_budget_per_turn: null
  injection_size_limit: null
providers:
- module: provider-anthropic
  source: git+https://github.com/microsoft/amplifier-module-provider-anthropic@main
  config:
    default_model: claude-sonnet-4-5
- module: provider-openai
  source: git+https://github.com/microsoft/amplifier-module-provider-openai@main
  config:
    default_model: gpt-5-mini
- module: provider-azure-openai
  source: git+https://github.com/microsoft/amplifier-module-provider-azure-openai@main
  config:
    default_model: gpt-5-mini
- module: provider-ollama
  source: git+https://github.com/microsoft/amplifier-module-provider-ollama@main
  config:
    default_model: llama3.2:3b
task:
  max_recursion_depth: 1
tools:
- module: tool-web
  source: git+https://github.com/microsoft/amplifier-module-tool-web@main
- module: tool-search
  source: git+https://github.com/microsoft/amplifier-module-tool-search@main
- module: tool-task
  source: git+https://github.com/microsoft/amplifier-module-tool-task@main
- module: tool-todo
  source: git+https://github.com/microsoft/amplifier-module-tool-todo@main
- module: tool-web
  source: git+https://github.com/microsoft/amplifier-module-tool-web@main
- module: tool-search
  source: git+https://github.com/microsoft/amplifier-module-tool-search@main
- module: tool-task
  source: git+https://github.com/microsoft/amplifier-module-tool-task@main
hooks:
- module: hooks-status-context
  source: git+https://github.com/microsoft/amplifier-module-hooks-status-context@main
  config:
    include_datetime: true
    datetime_include_timezone: false
- module: hooks-redaction
  source: git+https://github.com/microsoft/amplifier-module-hooks-redaction@main
  config:
    allowlist:
    - session_id
    - turn_id
    - span_id
    - parent_span_id
- module: hooks-logging
  source: git+https://github.com/microsoft/amplifier-module-hooks-logging@main
  config:
    mode: session-only
    session_log_template: ~/.amplifier/projects/{project}/sessions/{session_id}/events.jsonl
- module: hooks-todo-reminder
  source: git+https://github.com/microsoft/amplifier-module-hooks-todo-reminder@main
  config:
    inject_role: user
    priority: 10
- module: hooks-streaming-ui
  source: git+https://github.com/microsoft/amplifier-module-hooks-streaming-ui@main
- module: hooks-approval
  source: git+https://github.com/microsoft/amplifier-module-hooks-approval@main
  config:
    patterns:
    - rm -rf
    - sudo
    - DELETE
    - DROP
    auto_approve: false
- module: hooks-backup
  source: git+https://github.com/microsoft/amplifier-module-hooks-backup@main
  config:
    backup_dir: .amplifier/local/backups
    max_backups: 10
- module: hooks-scheduler-cost-aware
  source: git+https://github.com/microsoft/amplifier-module-hooks-scheduler-cost-aware@main
  config:
    budget_limit: 10.0
    warn_threshold: 0.8
- module: hooks-scheduler-heuristic
  source: git+https://github.com/microsoft/amplifier-module-hooks-scheduler-heuristic@main
  config:
    max_concurrent: 5
    batch_size: 10
agents:
  bug-hunter: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/developer-expertise/bug-hunter.md
  explorer: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/foundation/explorer.md
  modular-builder: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/developer-expertise/modular-builder.md
  post-task-cleanup: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/developer-expertise/post-task-cleanup.md
  researcher: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/developer-expertise/researcher.md
  zen-architect: https://raw.githubusercontent.com/payneio/amplifierd/refs/heads/main/registry/agents/developer-expertise/zen-architect.md
context:
  foundation: git+https://github.com/payneio/amplifierd@main#subdirectory=context/foundation
---
# Core Instructions

@foundation:context/shared/common-profile-base.md

---

Full capability configuration with comprehensive context:

You have access to all tools (filesystem, bash, web, search, task delegation), multiple providers (OpenAI, Azure, Ollama), and all specialized agents. Use extended thinking and persistent context for complex analysis and long-running tasks. Dangerous operations require explicit approval. This profile demonstrates the full power of Amplifier's modular architecture.
