# Amplifier Computation Platform - Project Context

## Overview

This repository contains Lakehouse, an **Intelligent Computation Platform** (the Amplifier Computing Platform or ACP). Lakehouse is an experimental project that demonstrates what it might look like for users to interact naturally with their computers through AI agents that work directly on their personal data, build custom tools on the fly, and proactively manage workflows.

**Vision Document**: See @amplifierd/docs/the-amplifier-computation-platform.md for the complete vision.

## Project Structure

### Core Components

1. **amplifierd/** - The Amplifier Daemon
   - FastAPI web service exposing Amplifier functionality over HTTP
   - Always-running daemon enabling reactive and scheduled workflows
   - See @amplifierd/README.md for details

2. **amplifier_library/** - Amplifier Library
   - Python library providing higher-level abstractions over Microsoft's Amplifier Core
   - Business logic layer between daemon transport and Amplifier Core execution
   - See @amplifier_library/README.md for architecture details

3. **webapp/** - React Web Application
   - Modern React + TypeScript UI for interacting with the daemon
   - Tech stack: React 19, TypeScript, Vite, TanStack Query, Tailwind CSS
   - See @webapp/README.md for development details

4. **notebooks/** - Jupyter Notebooks
   - Demonstrations of amplifier-core and amplifierd usage
   - Learning resources and examples

5. **guides/** - Documentation
   - Guides about Amplifier v2 concepts and usage

## Key Concepts

### Personal Data Lakehouse
- ACP works on **your data** in a directory you specify (the `data_dir`)
- Any directory can be "amplified" to become a project with its own context
- Integrates naturally with synced data (calendar, email, OneDrive, etc.)
- Privacy and control through local-first architecture

### Profile-Based Personalization
- Agents can be contextualized for different domains/situations
- Profiles define agent behavior (separate from project context)
- Can be switched within any chat session
- Built on Amplifier Core's flexible module composition

### Always-Running Intelligence
- Unlike CLI tools that only work when invoked, the daemon is always running
- Enables scheduled workflows, reactive automation, and meta-activities
- Can monitor conditions and kick off workflows automatically
- Examples: daily newspaper generation, lead dossier creation, self-improvement suggestions

### Project-Based Organization
- Each amplified directory becomes a project with:
  - Chat sessions with historical context
  - Default profiles and custom context
  - Project-specific workflows and automation
  - Any file organization you prefer

## Architecture Philosophy

This project follows the **"bricks and studs"** modular design philosophy:
- Each module is self-contained and regeneratable
- Clear contracts/interfaces between modules
- Ruthlessly simple implementations
- See @ai_context/MODULAR_DESIGN_PHILOSOPHY.md for details

Development follows:
- **Ruthless simplicity** over premature abstraction
- **Vertical slices** (end-to-end functionality) over perfect components
- **Purpose-driven execution** - understand "why" before "how"
- See @ai_context/IMPLEMENTATION_PHILOSOPHY.md for complete philosophy

## Technology Stack

### Backend (amplifierd)
- **Python 3.11+**
- **FastAPI** - Web framework
- **Amplifier Core** - Microsoft's AI orchestration system
- **Pydantic** - Data validation
- **uv** - Dependency management

### Frontend (webapp)
- **React 19** with TypeScript
- **Vite** - Build tool
- **React Router 7** - Routing
- **TanStack Query** - Server state
- **Tailwind CSS 4** - Styling
- **pnpm** - Package management

## Getting Started

```bash
# Prerequisites: Python 3.10+, Node.js 16+, pnpm, make, uv

# Install all dependencies
make install

# Run the daemon
make daemon-dev

# Run the webapp (in separate terminal)
make webapp-dev
```

Visit http://localhost:7777 in your browser.

**Configuration**: A `.amplifierd` directory is created, by default at `~/.amplifierd`. Configure the `data_dir` in `.amplifierd/config/daemon.yaml` to specify where ACP can access your data.

## Development Commands

All commands available via `make` - run `make help` to see available targets.

### Common Commands
- `make dev` - Start both daemon and webapp
- `make check` - Full validation (lint + typecheck + test). Beware: if imports are not used, they will be removed by the linter. If you don't want them removed, you should add them at the same time or after the code that needs them.
- `make test` - Run all tests
- `make install` - Install all dependencies

### Component-Specific
- `make daemon-dev` - Run daemon in development mode
- `make daemon-test` - Run daemon tests
- `make webapp-dev` - Run webapp development server
- `make webapp-build` - Build webapp for production

See @Makefile for complete list of targets.

## Important Documents

- @amplifierd/docs/the-amplifier-computation-platform.md - Vision document

## Testing

The webapp is run by the vite dev server and will restart whenever changes are made. There is no need to manually restart it when testing. The daemon should be restarted with `lakehouse restart --daemon-only`. This will correctly stop and restart the daemon on port 8420. Avoid starting up new daemons and webapps for testing.
