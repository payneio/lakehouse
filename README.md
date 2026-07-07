# Lakehouse

## Intelligent computation platform

Lakehouse is a [daemon](./lakehoused/README.md) and [webapp](./webapp/README.md) that provide an intelligent agent experience on top of your personal data.

Read more about the vision and design  in [The Intelligent Computation Platform](./lakehoused/docs/the-amplifier-computation-platform.md).

## Amplifier

This app uses [amplifier-core](https://github.com/microsoft/amplifier-core) under the hood, which is a Python library for building LLM-backed agents.

There are some resources for learning more about Amplifier here:

- [`guides`](./guides/README.md): Docs about Amplifier.
- [`notebooks/amplifier-core`](./notebooks/amplifier-core/README.md): Notebooks demonstrating how to use amplifier-core.
- [`notebooks/lakehoused`](./notebooks/lakehoused/README.md): Notebooks demonstrating how to use the lakehoused server.

To get a better handle on amplifier, feel free to explore the guides and notebooks, or run the daemon and webapp locally to poke around.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 16+
- pnpm
- make
- uv (Python package manager)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/payneio/lakehouse.git
cd lakehouse

# 2. Install dependencies
make install

# 3. Install the lakehouse CLI
cd lakehoused
uv tool install -e .
```

**Why editable mode (`-e`)?** The lakehouse CLI needs access to the full repository structure (both `lakehoused/` and `webapp/` directories). Editable mode ensures your (and Lakehouse) code changes take effect immediately without reinstalling.

### Usage

#### Running the stack

Service lifecycle (start/stop/restart) is managed **outside** the CLI. Use `make` for local
development, or a process manager such as systemd for a long-running deployment.

```bash
# Run daemon only (in foreground)
make daemon-dev

# Run webapp only (in separate terminal, in foreground)
make webapp-dev

# Run both (daemon in background, webapp in foreground)
make dev
```

**For auto-starting on reboot / long-running deployments**, see [DEPLOYMENT.md](./DEPLOYMENT.md).

#### The Lakehouse CLI

The CLI inspects the stack and registers projects (it does not manage lifecycle):

```bash
# Daemon/webapp status (daemon checked via its HTTP API)
lakehouse status

# Daemon logs from the systemd journal
lakehouse logs                 # last 50 lines
lakehouse logs -f              # follow live
lakehouse logs -u <unit>       # override unit (default: $LAKEHOUSED_SYSTEMD_UNIT)

# Register the current directory as a lakehouse project
lakehouse init                 # or: lakehouse init <path> --name "My Project"

# Open the webapp in a browser
lakehouse open
```

`lakehouse init` asks the daemon to create the directory's `.lakehouse` marker and register
it (the directory must live under the daemon's data root). It needs the daemon running and,
if a password gate is enabled, the password via `--password`, `LAKEHOUSED_AUTH_PASSWORD`, or
`~/.lakehoused/config/secrets.yaml`. `lakehouse logs` reads journald, so it targets a
systemd-managed daemon.

**Note:** Logs are written to `.lakehoused/logs/` (in your daemon's state directory).

### Access the Application

**Local access:**
```
http://localhost:5173
```

**Network access (from other devices):**
```
http://YOUR_SERVER_IP:5173
```

The webapp starts with `--host` flag, making it accessible from other devices on your network.

#### LAN Access

To access lakehouse from other devices on your local network (iPad, another laptop, etc.), see **[LAN.md](LAN.md)** for complete setup instructions.

⚠️ **Security:** LAN mode has no authentication. Only use on trusted networks.

### Configuration

A `.lakehoused` directory is created when you first run the daemon. Configure it by editing:

```
.lakehoused/config/daemon.yaml
```

**Configuration structure:**
```yaml
startup:
  auto_discover_profiles: true
  check_cache_on_startup: true
  # ... other startup settings

daemon:
  host: "127.0.0.1"
  port: 8420
  cors_origins:
    - "http://localhost:5173"
  # ... other runtime settings
```

**For LAN/network access configuration:** See [LAN.md](LAN.md)

After changing configuration, restart the daemon using whatever manages its lifecycle
(e.g. `make daemon-dev` in development, or `systemctl --user restart <service>` in a
systemd deployment — see [DEPLOYMENT.md](./DEPLOYMENT.md)).

### Common Tasks

**Check if services are running:**
```bash
lakehouse status
```

**View logs:**
```bash
lakehouse logs              # Show last 50 lines of both logs
lakehouse logs --daemon     # Show daemon logs only
lakehouse logs -f --webapp  # Follow webapp logs live (Ctrl+C to exit)
lakehouse logs -n 100       # Show last 100 lines
```

**Start/stop/restart services:**

Lifecycle is managed outside the CLI — use `make` (development) or your process manager
(e.g. systemd) as described in [DEPLOYMENT.md](./DEPLOYMENT.md).

**Log files location:**
```
.lakehoused/logs/lakehoused/daemon.log
.lakehoused/logs/webapp/webapp.log
```
(Located in your daemon's state directory)

### Troubleshooting

**Daemon won't start:**
- Check if port 8420 is already in use: `lsof -i :8420`
- Check `.lakehoused/config/daemon.yaml` for configuration errors
- Try running directly: `cd lakehoused && uv run python -m lakehoused`

**Webapp won't start:**
- Check if port 5173 is already in use: `lsof -i :5173`
- Verify dependencies are installed: `cd webapp && pnpm install`
- Check for errors: `cd webapp && pnpm run dev`

**CLI commands not found:**
- Ensure you ran `uv tool install -e .` from the `lakehoused` directory
- Check if uv tools are in PATH: `uv tool list`
- Reinstall if needed: `cd lakehoused && uv tool install --force -e .`
