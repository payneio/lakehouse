# Lakehouse

## What's in This Repository

### 1. `/guides/` - Generated Documentation
Comprehensive guides about Amplifier concepts, created by amplifier.v1 itself as a learning exercise.

**Contents**: agents, CLI, context, development, hooks, modules, mounts, orchestrators, profiles, tools

**Purpose**: Reference documentation to understand Amplifier's architecture and capabilities

### 2. `/notebooks/` - Interactive Tutorials

#### `/notebooks/amplifier-core/`
Jupyter notebooks demonstrating how to use the amplifier-core Python packages directly.

**Topics**: agents, hooks, modules, mounts

**Use**: Open these to learn how to interact with amplifier-core programmatically

#### `/notebooks/lakehoused/`
Jupyter notebooks demonstrating how to use the lakehoused REST API daemon.

**Topics**: getting started, sessions, messages, profiles, collections, modules, mounts, amplified directories

**Use**: Run the daemon first (`python -m lakehoused`), then open these notebooks to learn the API

### 3. `/lakehoused/` - REST API Daemon
A FastAPI web server that exposes amplifier-core functionality via REST API with SSE streaming.

**Purpose**: Provides HTTP/REST interface to Amplifier for web applications

**Default Port**: 8420

**Key Features**:
- Session lifecycle management
- Message operations with SSE streaming
- Collection and profile management
- Interactive API docs at http://localhost:8420/docs

**Architecture**:
```
lakehoused/
├── api/          # API layer
├── models/       # Pydantic models
├── routers/      # FastAPI endpoints
├── services/     # Business logic
└── main.py       # Application entry point
```

**Running**: `python -m lakehoused` or `uv run python -m lakehoused`

**Tech**: FastAPI, uvicorn, SSE-starlette, Pydantic

### 4. `/webapp/` - React Web UI
Modern web interface for interacting with the Amplifier system via the lakehoused API.

**Purpose**: User-friendly web UI for managing sessions, collections, and profiles

**Default Port**: 5173 (dev server)

**Tech Stack**:
- React 19 + TypeScript
- Vite (build tool)
- React Router 7 (routing)
- TanStack Query (state management)
- Tailwind CSS 4 (styling)

**Architecture**:
```
webapp/src/
├── api/          # API client functions
├── features/     # Feature modules (collections, directories, session)
├── components/   # React components (ui, layout)
├── pages/        # Route pages
└── types/        # TypeScript definitions
```

**Running**: `pnpm dev` (requires `pnpm install` first)

**Current Status**: Phase 1 complete (foundation), working on Phase 2 (collection management UI)

### 5. `/docs/` - Project Documentation
Comprehensive documentation about concepts, patterns, and workflows.

**Key Sections**:
- `01-concepts/` - Core concepts and architecture
- `04-advanced/` - Advanced features
- `design/` - Design intelligence framework
- `development_patterns/` - Best practices
- Various guides (THIS_IS_THE_WAY.md, WORKSPACE_PATTERN.md, etc.)

### Supporting Directories

- `/lakehouse_library/` - Core library layer (if present)
- `/registry/` - Configuration registry for agents, profiles, tools.
- `/.claude/` - Claude Code integration with custom agents
- `/tests/` - Test suite
- `/scripts/` - Utility scripts
- `/related-projects/` - Git submodules for related projects
- `/working/` - Scratch space

## Quick Commands

```bash
# Install dependencies
make install          # or: uv sync

# Run the daemon
python -m lakehoused  # API at http://localhost:8420

# Run the webapp
cd webapp && pnpm install && pnpm dev  # UI at http://localhost:5173

# Development checks
make check            # Format, lint, type-check
make test             # Run test suite
```

## Development Guidelines

### Code Standards
- **Python**: 3.11+, 120 char line length, full type hints
- **TypeScript**: Strict mode enabled
- **Formatting**: Ruff (Python), Prettier via Vite (TypeScript)
- **Package Management**: `uv` for Python, `pnpm` for Node.js

### Before Committing
1. Run `make check` to catch syntax, linting, and type errors
2. Start the daemon to verify it runs: `python -m lakehoused`
3. Test basic functionality
4. Stop the service (Ctrl+C)

### Key Principles
- **Simplicity First**: Keep code simple and maintainable
- **Test Thoroughly**: Verify changes before presenting as "done"
- **Modular Design**: Self-contained modules with clear contracts
- **Type Safety**: Use type hints (Python) and strict types (TypeScript)

## Typical Workflows

### Learning Amplifier
1. Read the guides in `/guides/`
2. Explore notebooks in `/notebooks/amplifier-core/`
3. Run the daemon and work through `/notebooks/lakehoused/`

### Working with the Daemon
1. Start: `python -m lakehoused`
2. View API docs: http://localhost:8420/docs
3. Test endpoints using Swagger UI or notebooks
4. Check logs for debugging

### Developing the Web UI
1. Ensure daemon is running on port 8420
2. Start dev server: `cd webapp && pnpm dev`
3. Access UI at http://localhost:5173
4. Edit components in `webapp/src/`
5. Hot reload updates automatically

## Project Context

**Repository Purpose**: Education and exploration workspace for learning Amplifier

**Not**: A production deployment or the main Amplifier repository

**Maturity**: Learning/experimental environment, frequent changes expected

**Key Insight**: This repo was created by having Amplifier teach itself - the guides and notebooks were generated by asking Amplifier to document and demonstrate its own capabilities.

---

**Last Updated**: 2025-12-02

**For**: AI agents working in this repository
