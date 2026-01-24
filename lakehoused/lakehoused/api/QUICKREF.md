# Amplifier Daemon API - Quick Reference

One-page reference for common operations.

## Base URL

```
http://localhost:8080/api/v1
```

## Common Workflows

### 1. Create & Use Session

```bash
# Create session
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "my-session", "profile": "code-reviewer"}' \
  | jq -r '.metadata.session_id'

# Save session ID
SESSION_ID="<from-above>"

# Execute prompt
curl -X POST "http://localhost:8080/api/v1/sessions/$SESSION_ID/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this code: def add(a,b): return a+b"}'

# Get history
curl "http://localhost:8080/api/v1/sessions/$SESSION_ID"

# Delete
curl -X DELETE "http://localhost:8080/api/v1/sessions/$SESSION_ID"
```

### 2. Single-Shot Execution

```bash
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain mocking vs stubbing", "profile": "test-writer"}'
```

### 3. Streaming Execution

```bash
curl -X POST http://localhost:8080/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{"prompt": "Write comprehensive tests", "profile": "test-writer"}'
```

### 4. Profile Management

```bash
# List profiles
curl http://localhost:8080/api/v1/profiles

# Get profile details
curl http://localhost:8080/api/v1/profiles/code-reviewer

# Set current profile
curl -X PUT http://localhost:8080/api/v1/profiles/current \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "test-writer"}'
```

## All Endpoints

### Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | Daemon status |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List sessions |
| POST | `/sessions` | Create session |
| GET | `/sessions/{id}` | Get session |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/sessions/{id}/execute` | Execute in session |
| GET | `/sessions/{id}/stream` | Stream events (SSE) |

### Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profiles` | List profiles |
| GET | `/profiles/{name}` | Get profile |
| GET | `/profiles/current` | Get current |
| PUT | `/profiles/current` | Set current |

### Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/execute` | Single-shot |
| POST | `/execute/stream` | Streaming (SSE) |

### Config

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get config |
| PUT | `/config` | Update config |
| GET | `/config/modules` | List modules |
| GET | `/config/providers` | List providers |

## Request Bodies

### Create Session

```json
{
  "name": "session-name",
  "profile": "profile-name",
  "tags": ["tag1", "tag2"]
}
```

### Execute

```json
{
  "prompt": "Your prompt here",
  "stream": false
}
```

### Set Profile

```json
{
  "profile_name": "code-reviewer"
}
```

### Update Config

```json
{
  "retry_attempts": 5,
  "debug": true
}
```

## Response Formats

### Success (Session)

```json
{
  "metadata": {
    "session_id": "uuid",
    "name": "string",
    "turns": 0
  },
  "messages": [],
  "context": {},
  "config": {}
}
```

### Success (Execution)

```json
{
  "content": "Response text...",
  "metadata": {
    "tokens": 250,
    "duration_ms": 1200
  }
}
```

### Error

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Description",
    "details": {}
  }
}
```

## SSE Events

### Event Format

```
event: <type>
data: <json>

```

### Event Types

| Event | Data | Meaning |
|-------|------|---------|
| `message` | `{"content": "..."}` | Content chunk |
| `metadata` | `{"tokens": N}` | Progress update |
| `error` | `{"code": "...", "message": "..."}` | Error |
| `done` | `{"status": "completed"}` | Complete |

## Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| `INVALID_REQUEST` | 400 | Bad request |
| `NOT_FOUND` | 404 | Resource missing |
| `SESSION_NOT_FOUND` | 404 | Invalid session ID |
| `PROFILE_NOT_FOUND` | 404 | Invalid profile |
| `EXECUTION_FAILED` | 500 | LLM failed |
| `INTERNAL_ERROR` | 500 | Server error |

## Python Examples

### Basic Session

```python
import requests

# Create session
resp = requests.post(
    'http://localhost:8080/api/v1/sessions',
    json={'name': 'my-session', 'profile': 'code-reviewer'}
)
session_id = resp.json()['metadata']['session_id']

# Execute
resp = requests.post(
    f'http://localhost:8080/api/v1/sessions/{session_id}/execute',
    json={'prompt': 'Review this code'}
)
print(resp.json()['content'])
```

### Streaming

```python
import requests
import json

resp = requests.post(
    'http://localhost:8080/api/v1/execute/stream',
    json={'prompt': 'Write tests'},
    stream=True,
    headers={'Accept': 'text/event-stream'}
)

for line in resp.iter_lines():
    if line.startswith(b'data:'):
        data = json.loads(line[5:])
        print(data)
```

## JavaScript Examples

### Basic Fetch

```javascript
// Create session
const resp = await fetch('http://localhost:8080/api/v1/sessions', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    name: 'my-session',
    profile: 'code-reviewer'
  })
});
const {metadata: {session_id}} = await resp.json();

// Execute
const execResp = await fetch(
  `http://localhost:8080/api/v1/sessions/${session_id}/execute`,
  {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt: 'Review code'})
  }
);
const {content} = await execResp.json();
console.log(content);
```

### SSE Streaming

```javascript
const eventSource = new EventSource(
  `http://localhost:8080/api/v1/sessions/${session_id}/stream`
);

eventSource.addEventListener('message', (e) => {
  const {content} = JSON.parse(e.data);
  console.log(content);
});

eventSource.addEventListener('done', (e) => {
  console.log('Done:', JSON.parse(e.data));
  eventSource.close();
});
```

## Configuration

### Default Locations

```
Sessions:  ~/.ccsdk/sessions/
Logs:      ~/.ccsdk/logs/
Cache:     ~/.ccsdk/cache/
```

### Start Daemon

```bash
lakehoused start --port 8080
```

### Enable Debug

```bash
# Via CLI
lakehoused start --debug

# Via API
curl -X PUT http://localhost:8080/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"debug": true}'
```

## Testing

### Health Check

```bash
curl http://localhost:8080/api/v1/health
```

### Full Status

```bash
curl http://localhost:8080/api/v1/status | jq
```

### List All Resources

```bash
# Sessions
curl http://localhost:8080/api/v1/sessions | jq

# Profiles
curl http://localhost:8080/api/v1/profiles | jq

# Modules
curl http://localhost:8080/api/v1/config/modules | jq

# Providers
curl http://localhost:8080/api/v1/config/providers | jq
```

## Tips

### Save Session ID

```bash
SESSION_ID=$(curl -s -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}' \
  | jq -r '.metadata.session_id')

echo $SESSION_ID
```

### Pretty Print JSON

```bash
curl http://localhost:8080/api/v1/sessions | jq '.'
```

### Filter Sessions

```bash
# Last 30 days
curl 'http://localhost:8080/api/v1/sessions?days_back=30'

# By tags
curl 'http://localhost:8080/api/v1/sessions?tags=review,python'
```

### Error Handling

```bash
# Check status code
curl -w "%{http_code}" http://localhost:8080/api/v1/sessions/invalid

# See error details
curl http://localhost:8080/api/v1/sessions/invalid | jq '.error'
```

## Resources

- **Full Docs**: `README.md`
- **Examples**: `EXAMPLES.md`
- **Contract**: `CONTRACT.md`
- **OpenAPI**: `openapi.yaml`
