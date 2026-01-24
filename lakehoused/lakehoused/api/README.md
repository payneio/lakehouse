# Amplifier Daemon API

REST API for the Amplifier daemon - exposes amplifier CLI functionality as HTTP endpoints.

## Overview

The Amplifier Daemon API provides HTTP access to amplifier's core functionality:
- **Session Management**: Create, resume, and manage persistent conversation contexts
- **Profile Management**: Switch between different agent configurations
- **Execution**: Run single-shot or streaming LLM interactions
- **Configuration**: Manage daemon settings and view available resources

## Quick Start

### Start the daemon

```bash
lakehoused start
```

### Check health

```bash
curl http://localhost:8080/api/v1/health
```

### Create a session

```bash
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "my-session", "profile": "code-reviewer"}'
```

### Execute in session

```bash
curl -X POST http://localhost:8080/api/v1/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this code for bugs"}'
```

## Architecture

### Design Philosophy

This API follows the "bricks and studs" philosophy:
- **The Contract (Studs)**: OpenAPI spec defines the stable interface
- **The Implementation (Bricks)**: Internal code can be regenerated from the contract
- **Regeneratable**: Modules can be rebuilt without breaking consumers

### Key Principles

1. **Contract-First**: API spec drives implementation
2. **Minimal & Clear**: Only essential endpoints, no premature features
3. **Consistent Errors**: Standard error response format
4. **Streaming Support**: SSE for long-running operations
5. **File-Based Persistence**: JSON files for sessions (simple, debuggable)

## Core Concepts

### Session

A **session** is a persistent conversation context with Claude:
- Maintains conversation history
- Preserves context across multiple prompts
- Stored as JSON files in session directory
- Resumable after daemon restart

**Lifecycle**:
```
POST /sessions → GET /sessions/{id} → POST /sessions/{id}/execute → DELETE /sessions/{id}
```

### Profile

A **profile** is an agent configuration:
- System prompt defining agent behavior
- Tool permissions (allowed/disallowed tools)
- Context files to include
- Maximum conversation turns

**Example profiles**:
- `code-reviewer`: Reviews code for bugs and improvements
- `test-writer`: Generates unit tests
- `documentation-writer`: Creates documentation

### Execution

**Single-shot execution** (`POST /execute`):
- No session persistence
- Quick one-off prompts
- Useful for stateless operations

**Session execution** (`POST /sessions/{id}/execute`):
- Maintains conversation context
- Builds on previous messages
- Session state persisted after each turn

## Endpoints

### Status Operations

#### `GET /health`

Quick health check.

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

#### `GET /status`

Detailed daemon status.

**Response**:
```json
{
  "status": "running",
  "active_sessions": 2,
  "total_sessions": 15,
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "memory_mb": 256
}
```

### Session Operations

#### `GET /sessions`

List all sessions.

**Query Parameters**:
- `days_back` (int, default: 7): How many days back to look
- `tags` (string): Comma-separated tags to filter by

**Response**:
```json
{
  "sessions": [
    {
      "session_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "code-review-session",
      "created_at": "2025-01-20T10:00:00Z",
      "updated_at": "2025-01-20T10:30:00Z",
      "turns": 5,
      "tags": ["review", "python"]
    }
  ]
}
```

#### `POST /sessions`

Create a new session.

**Request**:
```json
{
  "name": "my-session",
  "profile": "code-reviewer",
  "tags": ["review", "python"]
}
```

**Response** (201):
```json
{
  "metadata": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "my-session",
    "created_at": "2025-01-20T10:00:00Z",
    "updated_at": "2025-01-20T10:00:00Z",
    "turns": 0,
    "tags": ["review", "python"]
  },
  "messages": [],
  "context": {},
  "config": {}
}
```

#### `GET /sessions/{session_id}`

Get complete session details including conversation history.

**Response**:
```json
{
  "metadata": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "my-session",
    "turns": 2,
    "total_tokens": 450,
    "cost_usd": 0.05
  },
  "messages": [
    {
      "role": "user",
      "content": "Review this function",
      "timestamp": "2025-01-20T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Here's my review...",
      "timestamp": "2025-01-20T10:00:05Z",
      "metadata": {
        "tokens": 200
      }
    }
  ]
}
```

#### `POST /sessions/{session_id}/execute`

Execute a prompt in an existing session.

**Request**:
```json
{
  "prompt": "Review this function for potential bugs",
  "stream": false
}
```

**Response**:
```json
{
  "content": "I've analyzed the function and found...",
  "metadata": {
    "tokens": 250,
    "duration_ms": 1200,
    "cost_usd": 0.025
  }
}
```

#### `GET /sessions/{session_id}/stream`

Stream session events via Server-Sent Events.

**Event Types**:
- `message`: Content chunk from LLM
- `metadata`: Session metadata update
- `error`: Error occurred
- `done`: Execution completed

**Example stream**:
```
event: message
data: {"content": "Here is my analysis..."}

event: metadata
data: {"tokens": 150, "duration_ms": 1200}

event: done
data: {"status": "completed"}
```

#### `DELETE /sessions/{session_id}`

Delete a session permanently.

**Response**: 204 No Content

### Profile Operations

#### `GET /profiles`

List all available profiles.

**Response**:
```json
{
  "profiles": [
    {
      "name": "code-reviewer",
      "description": "Reviews code for bugs and improvements"
    },
    {
      "name": "test-writer",
      "description": "Generates unit tests"
    }
  ]
}
```

#### `GET /profiles/{profile_name}`

Get complete profile configuration.

**Response**:
```json
{
  "name": "code-reviewer",
  "description": "Reviews code for bugs and improvements",
  "system_prompt": "You are an expert code reviewer...",
  "allowed_tools": ["read", "grep"],
  "disallowed_tools": ["write", "bash"],
  "max_turns": 5
}
```

#### `GET /profiles/current`

Get the currently active profile.

#### `PUT /profiles/current`

Set the active profile.

**Request**:
```json
{
  "profile_name": "code-reviewer"
}
```

### Execution Operations

#### `POST /execute`

Single-shot execution without session persistence.

**Request**:
```json
{
  "prompt": "Explain this code snippet",
  "profile": "code-reviewer"
}
```

**Response**:
```json
{
  "content": "This code snippet...",
  "metadata": {
    "tokens": 150,
    "duration_ms": 800
  }
}
```

#### `POST /execute/stream`

Streaming execution via Server-Sent Events.

**Request**:
```json
{
  "prompt": "Write a detailed analysis",
  "profile": "analyst"
}
```

**Response**: SSE stream with `message` and `done` events

### Configuration Operations

#### `GET /config`

Get current daemon configuration.

**Response**:
```json
{
  "default_agent": "code-reviewer",
  "retry_attempts": 3,
  "environment": {
    "working_directory": "/home/user/project",
    "session_directory": "/home/user/.ccsdk/sessions",
    "log_directory": "/home/user/.ccsdk/logs",
    "cache_directory": "/home/user/.ccsdk/cache",
    "debug": false
  }
}
```

#### `PUT /config`

Update daemon configuration (partial updates supported).

**Request**:
```json
{
  "retry_attempts": 5,
  "debug": true
}
```

#### `GET /config/modules`

List available amplifier modules.

#### `GET /config/providers`

List configured LLM providers.

**Response**:
```json
{
  "providers": [
    {
      "name": "anthropic",
      "type": "anthropic",
      "available": true
    },
    {
      "name": "openai",
      "type": "openai",
      "available": false
    }
  ]
}
```

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {
      "field": "additional context"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Missing or invalid request fields |
| `NOT_FOUND` | 404 | Resource not found (session, profile, etc.) |
| `PROFILE_NOT_FOUND` | 404 | Specified profile doesn't exist |
| `SESSION_NOT_FOUND` | 404 | Session ID not found |
| `EXECUTION_FAILED` | 500 | LLM execution failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SDK_ERROR` | 500 | Claude SDK error |

### Example Error Responses

**Missing required field**:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field 'prompt'",
    "details": {
      "field": "prompt"
    }
  }
}
```

**Session not found**:
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found",
    "details": {
      "session_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }
}
```

**Execution failed**:
```json
{
  "error": {
    "code": "EXECUTION_FAILED",
    "message": "Failed to execute prompt after 3 retries",
    "details": {
      "cause": "SDK connection timeout",
      "retries": 3
    }
  }
}
```

## Streaming (SSE)

The API uses Server-Sent Events for streaming responses.

### SSE Event Format

```
event: <event_type>
data: <json_data>

```

### Event Types

#### `message`

Content chunk from LLM.

```
event: message
data: {"content": "This is part of the response..."}
```

#### `metadata`

Session metadata update.

```
event: metadata
data: {"tokens": 150, "duration_ms": 1200}
```

#### `error`

Error occurred during execution.

```
event: error
data: {"code": "EXECUTION_FAILED", "message": "Connection timeout"}
```

#### `done`

Execution completed successfully.

```
event: done
data: {"status": "completed", "tokens": 250}
```

### Client Example (JavaScript)

```javascript
const eventSource = new EventSource(
  'http://localhost:8080/api/v1/sessions/123e4567-e89b-12d3-a456-426614174000/stream'
);

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Content:', data.content);
});

eventSource.addEventListener('done', (event) => {
  const data = JSON.parse(event.data);
  console.log('Completed:', data);
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  console.error('Error:', event);
  eventSource.close();
});
```

### Client Example (Python)

```python
import requests
import json

response = requests.get(
    'http://localhost:8080/api/v1/sessions/123e4567-e89b-12d3-a456-426614174000/stream',
    stream=True
)

for line in response.iter_lines():
    if line.startswith(b'data:'):
        data = json.loads(line[5:])
        print(data)
```

## Concurrency

The daemon supports multiple concurrent operations:

### Multi-Session Concurrency

- Multiple sessions can be active simultaneously
- Each session maintains independent state
- Session operations are thread-safe

### Long-Running Operations

Long-running LLM operations are handled via:
1. **Async execution**: Non-blocking request handling
2. **SSE streaming**: Real-time progress updates
3. **Session persistence**: State saved after each turn

### Recommended Patterns

**For interactive applications**:
- Use SSE streaming endpoints (`/sessions/{id}/stream`, `/execute/stream`)
- Display real-time progress to users
- Handle connection interruptions gracefully

**For batch processing**:
- Create sessions for related operations
- Use non-streaming endpoints for simpler code
- Poll `/sessions/{id}` for status if needed

## File Storage

Sessions are persisted as JSON files in the session directory (default: `~/.ccsdk/sessions`).

### Session File Format

```json
{
  "metadata": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "my-session",
    "created_at": "2025-01-20T10:00:00",
    "updated_at": "2025-01-20T10:30:00",
    "turns": 5,
    "total_tokens": 1500,
    "cost_usd": 0.15,
    "duration_seconds": 1800,
    "tags": ["review", "python"]
  },
  "messages": [
    {
      "role": "user",
      "content": "Review this code",
      "timestamp": "2025-01-20T10:00:00"
    }
  ],
  "context": {},
  "config": {}
}
```

### File Naming

Sessions are stored as `{session_id}.json` in the session directory.

### Backup & Restoration

Sessions can be backed up by copying the session directory:

```bash
# Backup
cp -r ~/.ccsdk/sessions ~/backup/sessions-$(date +%Y%m%d)

# Restore
cp -r ~/backup/sessions-20250120 ~/.ccsdk/sessions
```

## API Versioning

The API uses URL path versioning: `/api/v1/...`

### Versioning Strategy

1. **Stay on v1 as long as possible**: Add optional fields, don't create v2 prematurely
2. **Additive changes are safe**: New endpoints, optional fields, additional response data
3. **Breaking changes require new version**: Changed field types, removed fields, changed semantics
4. **Version entire API, not individual endpoints**: Consistency across all endpoints

### When to Create v2

Only create v2 when breaking changes are unavoidable:
- Fundamental architecture changes
- Incompatible data model changes
- Changed core semantics

## Best Practices

### Session Management

**DO**:
- Create sessions for related conversation flows
- Use meaningful session names
- Tag sessions for organization
- Clean up old sessions periodically

**DON'T**:
- Create a new session for every request (use single-shot execution instead)
- Store sensitive data in session context
- Rely on sessions lasting forever (implement backups)

### Error Handling

**DO**:
- Check HTTP status codes
- Parse error response for details
- Implement retry logic with exponential backoff
- Log errors with full context

**DON'T**:
- Ignore error details
- Retry immediately without backoff
- Assume errors are transient

### Streaming

**DO**:
- Handle connection interruptions
- Parse SSE events properly
- Close connections when done
- Implement timeouts

**DON'T**:
- Buffer entire response before processing
- Ignore error events
- Leave connections open indefinitely

## Examples

### Complete Session Workflow

```bash
# 1. Create session
SESSION_ID=$(curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "code-review", "profile": "code-reviewer"}' \
  | jq -r '.metadata.session_id')

# 2. Execute first prompt
curl -X POST "http://localhost:8080/api/v1/sessions/$SESSION_ID/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this function: def add(a, b): return a + b"}'

# 3. Execute follow-up
curl -X POST "http://localhost:8080/api/v1/sessions/$SESSION_ID/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Are there any edge cases I should handle?"}'

# 4. Get full history
curl "http://localhost:8080/api/v1/sessions/$SESSION_ID"

# 5. Clean up
curl -X DELETE "http://localhost:8080/api/v1/sessions/$SESSION_ID"
```

### Streaming Example

```bash
# Stream execution
curl -X POST http://localhost:8080/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a detailed code review", "profile": "code-reviewer"}'
```

### Profile Management

```bash
# List profiles
curl http://localhost:8080/api/v1/profiles

# Get specific profile
curl http://localhost:8080/api/v1/profiles/code-reviewer

# Set current profile
curl -X PUT http://localhost:8080/api/v1/profiles/current \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "test-writer"}'
```

## Development

### Running Locally

```bash
# Start daemon
lakehoused start --port 8080

# View logs
tail -f ~/.ccsdk/logs/lakehoused.log

# Stop daemon
lakehoused stop
```

### Testing the API

```bash
# Health check
curl http://localhost:8080/api/v1/health

# Run all tests
pytest tests/api/

# Specific test
pytest tests/api/test_sessions.py -v
```

### Debugging

Enable debug mode:

```bash
lakehoused start --debug
```

Or via API:

```bash
curl -X PUT http://localhost:8080/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"debug": true}'
```

## OpenAPI Specification

The complete OpenAPI specification is available at: `openapi.yaml`

View in Swagger UI:
```bash
# Install swagger-ui
npm install -g swagger-ui-cli

# Serve spec
swagger-ui lakehoused/api/openapi.yaml
```

## Support

- **Issues**: https://github.com/microsoft/amplifier/issues
- **Discussions**: https://github.com/microsoft/amplifier/discussions
- **Documentation**: https://github.com/microsoft/amplifier/docs
