# Lakehouse

## Intelligent computation platform

Lakehouse is a [daemon](./amplifierd/README.md) and [webapp](./webapp/README.md) that provide an intelligent agent experience on top of your personal data.

Read more about the vision and design  in [The Intelligent Computation Platform](./amplifierd/docs/the-amplifier-computation-platform.md).

## Amplifier

This app uses [amplifier-core](https://github.com/microsoft/amplifier-core) under the hood, which is a Python library for building LLM-backed agents.

There are some resources for learning more about Amplifier here:

- [`guides`](./guides/README.md): Docs about Amplifier.
- [`notebooks/amplifier-core`](./notebooks/amplifier-core/README.md): Notebooks demonstrating how to use amplifier-core.
- [`notebooks/amplifierd`](./notebooks/amplifierd/README.md): Notebooks demonstrating how to use the amplifierd server.

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
cd amplifierd
uv tool install -e .
```

**Why editable mode (`-e`)?** The lakehouse CLI needs access to the full repository structure (both `amplifierd/` and `webapp/` directories). Editable mode ensures your (and Lakehouse) code changes take effect immediately without reinstalling.

### Usage

#### Using the Lakehouse CLI (Recommended)

```bash
# Start both daemon and webapp (runs in background)
lakehouse start

# Check status
lakehouse status

# View logs
lakehouse logs              # Show both daemon and webapp logs
lakehouse logs --daemon     # Show daemon logs only
lakehouse logs -f --webapp  # Follow webapp logs live

# Restart services
lakehouse restart

# Stop services
lakehouse stop

# Open webapp in browser
lakehouse open
```

**Note:** Services run in the background and logs are written to `.amplifierd/logs/` (in your daemon's state directory).

**Keep it running after disconnect:**

Services already run in the background, but will stop if your SSH session ends. To keep them running:

**Option 1: nohup (Simplest)**
```bash
# Start services that survive disconnect
nohup lakehouse start &

# Check status
lakehouse status

# View logs
lakehouse logs -f
```

**Option 2: tmux (Better for control)**
```bash
# Run in tmux session
tmux new -s lakehouse
lakehouse start
# Press Ctrl+B, then D to detach

# Reconnect later
tmux attach -t lakehouse
```

**For auto-starting on reboot**, see [DEPLOYMENT.md](./DEPLOYMENT.md).

#### Using Make Commands (Alternative)

```bash
# Run daemon only (in foreground)
make daemon-dev

# Run webapp only (in separate terminal, in foreground)
make webapp-dev

# Run both (daemon in background, webapp in foreground)
make dev
```

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

A `.amplifierd` directory is created when you first run the daemon. Configure it by editing:

```
.amplifierd/config/daemon.yaml
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

After changing configuration, restart the daemon:
```bash
lakehouse stop
lakehouse start
```

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

**Restart services:**
```bash
lakehouse restart              # Restart both
lakehouse restart --daemon-only  # Restart only daemon
```

**Start/stop individual services:**
```bash
lakehouse start --daemon-only   # Start only daemon
lakehouse start --webapp-only   # Start only webapp
lakehouse stop --daemon-only    # Stop only daemon
```

**Log files location:**
```
.amplifierd/logs/amplifierd/daemon.log
.amplifierd/logs/webapp/webapp.log
```
(Located in your daemon's state directory)

### Troubleshooting

**Daemon won't start:**
- Check if port 8420 is already in use: `lsof -i :8420`
- Check `.amplifierd/config/daemon.yaml` for configuration errors
- Try running directly: `cd amplifierd && uv run python -m amplifierd`

**Webapp won't start:**
- Check if port 5173 is already in use: `lsof -i :5173`
- Verify dependencies are installed: `cd webapp && pnpm install`
- Check for errors: `cd webapp && pnpm run dev`

**CLI commands not found:**
- Ensure you ran `uv tool install -e .` from the `amplifierd` directory
- Check if uv tools are in PATH: `uv tool list`
- Reinstall if needed: `cd amplifierd && uv tool install --force -e .`
