# amplifierd

REST API daemon for amplifier-core with SSE streaming support.

## Overview

`amplifierd` exposes the `amplifier_library` functionality via a FastAPI REST API with Server-Sent Events (SSE) streaming for real-time execution updates.

## Architecture

```
amplifierd/
├── models/           # Pydantic request/response models
│   ├── requests.py
│   ├── responses.py
│   └── errors.py
├── routers/          # FastAPI routers
│   ├── sessions.py   # Session lifecycle
│   ├── messages.py   # Message operations & SSE streaming
│   └── status.py     # Health & status
├── streaming.py      # SSE utilities
├── main.py          # FastAPI application
└── __main__.py      # CLI entry point
```

## Running the Daemon

### Using Python module

```bash
python -m amplifierd
# or with uv
uv run python -m amplifierd
```

### Using uvicorn directly

```bash
uvicorn amplifierd.main:app --host 0.0.0.0 --port 8420
```

### Configuration

Configuration is loaded from `.amplifierd/config/daemon.yaml`:

```yaml
# Startup behavior
startup:
  auto_discover_profiles: true
  auto_compile_profiles: true
  check_cache_on_startup: true
  update_stale_caches: false
  parallel_compilation: true
  max_parallel_workers: 4

# Runtime settings
daemon:
  # Server settings
  host: "127.0.0.1"  # Use "0.0.0.0" for LAN access
  port: 8420
  workers: 1
  log_level: "INFO"

  # CORS configuration
  cors_origins:
    - "http://localhost:5173"  # Add your LAN URLs here for network access

  # Cache and monitoring
  watch_for_changes: false
  watch_interval_seconds: 60
  cache_ttl_hours: null
  enable_metrics: true
```

**For LAN access:** See [../LAN.md](../LAN.md) for complete setup including CORS configuration.

Environment variables override YAML settings (prefixed with `AMPLIFIERD_`):

```bash
# Override server port
AMPLIFIERD_PORT=8421 python -m amplifierd

# Use home directory for data
AMPLIFIERD_DATA_PATH="~" python -m amplifierd

# Use custom directory
AMPLIFIERD_DATA_PATH="/path/to/custom/data" python -m amplifierd
```

**Path Expansion:**
- Absolute paths (e.g., `/data`) are used as-is
- Tilde paths (e.g., `~` or `~/amplifier`) expand to your home directory
- Relative paths (e.g., `./data`) resolve to absolute paths from current directory

## API Endpoints

### Sessions

- `POST /api/v1/sessions` - Create new session
- `GET /api/v1/sessions` - List all sessions
- `GET /api/v1/sessions/{session_id}` - Get session details
- `POST /api/v1/sessions/{session_id}/resume` - Resume session
- `DELETE /api/v1/sessions/{session_id}` - Delete session

### Messages

- `POST /api/v1/sessions/{session_id}/messages` - Send message (sync)
- `GET /api/v1/sessions/{session_id}/messages` - Get transcript
- `POST /api/v1/sessions/{session_id}/execute` - Execute with SSE streaming

### Status

- `GET /api/v1/status` - Get daemon status
- `GET /api/v1/health` - Health check

## SSE Streaming

The `/execute` endpoint uses Server-Sent Events for streaming responses:

```javascript
const eventSource = new EventSource('/api/v1/sessions/{session_id}/execute');

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Content:', data.content);
});

eventSource.addEventListener('done', (event) => {
  console.log('Execution complete');
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  console.error('Error:', data.error);
  eventSource.close();
});
```

## Interactive API Documentation

Once running, visit:

- **Swagger UI**: http://localhost:8420/docs
- **ReDoc**: http://localhost:8420/redoc
- **OpenAPI Schema**: http://localhost:8420/openapi.json

## Development

```bash
# Install dependencies
uv sync

# Run checks
make check

# Run tests
make test

# Start daemon
uv run python -m amplifierd
```

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sse-starlette` - Server-Sent Events support
- `pydantic` - Data validation
- `amplifier_library` - Core library layer
