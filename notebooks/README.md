# Amplifier Notebooks

Jupyter notebooks for exploring and developing Amplifier daemon functionality.

## Setup

First time setup:

```bash
cd notebooks
uv venv
uv sync
```

## Running Notebooks

Activate the environment and start Jupyter:

```bash
cd notebooks
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
jupyter notebook
```

Or use the Makefile target from the project root:

```bash
make notebooks-run
```

## Organization

- `amplifierd/` - Daemon functionality notebooks
  - 01-getting-started.ipynb
  - 02-sessions-and-messages.ipynb
  - 03-profile-management.ipynb
  - 04-collection-management.ipynb
  - 05-module-management.ipynb
  - 06-mount-plan-generation.ipynb
  - 07-session-lifecycle.ipynb
  - 08-amplified-directories.ipynb

- `amplifier-core/` - Core functionality notebooks
  - amplifier-agents.ipynb
  - amplifier-hooks.ipynb
  - amplifier-modules.ipynb
  - amplifier-mounts.ipynb

## Development

The notebooks environment uses an editable install of the daemon (`../amplifierd`), which means:
- Changes to daemon code are immediately visible in notebooks
- No reinstall needed when modifying daemon code
- Always testing against current daemon implementation

## Adding Dependencies

To add a new package to the notebooks environment:

```bash
cd notebooks
uv add <package-name>
```

## Troubleshooting

**Import errors**: Make sure you've run `uv sync` and activated the virtual environment.

**Daemon changes not visible**: The editable install should make changes immediately available. If not, try restarting the Jupyter kernel.
