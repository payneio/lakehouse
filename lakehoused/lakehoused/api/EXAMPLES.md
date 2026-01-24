# API Examples

Comprehensive examples for all Amplifier Daemon API endpoints.

## Table of Contents

- [Session Operations](#session-operations)
- [Profile Operations](#profile-operations)
- [Execution Operations](#execution-operations)
- [Configuration Operations](#configuration-operations)
- [Error Examples](#error-examples)
- [Streaming Examples](#streaming-examples)

## Session Operations

### Create Session

**Request**:
```http
POST /api/v1/sessions HTTP/1.1
Content-Type: application/json

{
  "name": "code-review-session",
  "profile": "code-reviewer",
  "tags": ["review", "python", "security"]
}
```

**Response (201 Created)**:
```json
{
  "metadata": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "code-review-session",
    "created_at": "2025-01-20T15:30:00Z",
    "updated_at": "2025-01-20T15:30:00Z",
    "turns": 0,
    "total_tokens": 0,
    "cost_usd": 0.0,
    "duration_seconds": 0.0,
    "tags": ["review", "python", "security"]
  },
  "messages": [],
  "context": {},
  "config": {
    "profile": "code-reviewer",
    "max_turns": 10
  }
}
```

### List Sessions

**Request**:
```http
GET /api/v1/sessions?days_back=30&tags=review,python HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "code-review-session",
      "created_at": "2025-01-20T15:30:00Z",
      "updated_at": "2025-01-20T15:45:00Z",
      "turns": 3,
      "tags": ["review", "python", "security"]
    },
    {
      "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "name": "refactoring-discussion",
      "created_at": "2025-01-19T10:00:00Z",
      "updated_at": "2025-01-19T11:30:00Z",
      "turns": 8,
      "tags": ["review", "python", "refactoring"]
    }
  ]
}
```

### Get Session Details

**Request**:
```http
GET /api/v1/sessions/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "metadata": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "code-review-session",
    "created_at": "2025-01-20T15:30:00Z",
    "updated_at": "2025-01-20T15:45:00Z",
    "turns": 3,
    "total_tokens": 1250,
    "cost_usd": 0.0375,
    "duration_seconds": 45.8,
    "tags": ["review", "python", "security"]
  },
  "messages": [
    {
      "role": "user",
      "content": "Review this authentication function for security issues",
      "timestamp": "2025-01-20T15:30:00Z"
    },
    {
      "role": "assistant",
      "content": "I've analyzed the authentication function. Here are the security concerns I found:\n\n1. Password comparison uses == instead of secure comparison\n2. No rate limiting on failed attempts\n3. Passwords stored in plain text\n\nRecommendations:\n- Use secrets.compare_digest() for password comparison\n- Implement rate limiting with exponential backoff\n- Hash passwords with bcrypt or argon2",
      "timestamp": "2025-01-20T15:30:15Z",
      "metadata": {
        "tokens": 450,
        "duration_ms": 15000
      }
    },
    {
      "role": "user",
      "content": "Can you show me an example of implementing bcrypt hashing?",
      "timestamp": "2025-01-20T15:32:00Z"
    },
    {
      "role": "assistant",
      "content": "Here's a secure implementation using bcrypt:\n\n```python\nimport bcrypt\n\ndef hash_password(password: str) -> str:\n    \"\"\"Hash password securely using bcrypt.\"\"\"\n    salt = bcrypt.gensalt(rounds=12)\n    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)\n    return hashed.decode('utf-8')\n\ndef verify_password(password: str, hashed: str) -> bool:\n    \"\"\"Verify password against hash.\"\"\"\n    return bcrypt.checkpw(\n        password.encode('utf-8'),\n        hashed.encode('utf-8')\n    )\n```\n\nKey points:\n- rounds=12 provides good security/performance balance\n- Always encode strings to bytes\n- bcrypt.checkpw is constant-time comparison",
      "timestamp": "2025-01-20T15:32:18Z",
      "metadata": {
        "tokens": 380,
        "duration_ms": 18000
      }
    }
  ],
  "context": {
    "language": "python",
    "focus": "security"
  },
  "config": {
    "profile": "code-reviewer",
    "max_turns": 10
  }
}
```

### Execute in Session

**Request**:
```http
POST /api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/execute HTTP/1.1
Content-Type: application/json

{
  "prompt": "What about SQL injection vulnerabilities?",
  "stream": false
}
```

**Response (200 OK)**:
```json
{
  "content": "Good question! Let me check for SQL injection risks:\n\n1. **Parameterized Queries**: Always use parameterized queries or prepared statements:\n\n```python\n# BAD - Vulnerable to SQL injection\nquery = f\"SELECT * FROM users WHERE username = '{username}'\"\n\n# GOOD - Safe from SQL injection\nquery = \"SELECT * FROM users WHERE username = %s\"\ncursor.execute(query, (username,))\n```\n\n2. **ORM Usage**: If using an ORM like SQLAlchemy:\n\n```python\n# Safe - ORM handles parameterization\nuser = session.query(User).filter_by(username=username).first()\n```\n\n3. **Input Validation**: Still validate input even with parameterized queries:\n\n```python\nimport re\n\ndef validate_username(username: str) -> bool:\n    # Only alphanumeric and underscore\n    return bool(re.match(r'^[a-zA-Z0-9_]{3,20}$', username))\n```\n\nBest practice: Never concatenate user input into SQL queries.",
  "metadata": {
    "tokens": 420,
    "duration_ms": 16500,
    "cost_usd": 0.0126,
    "model": "claude-3-5-sonnet-20250120"
  }
}
```

### Delete Session

**Request**:
```http
DELETE /api/v1/sessions/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
```

**Response (204 No Content)**:
```
(empty body)
```

## Profile Operations

### List Profiles

**Request**:
```http
GET /api/v1/profiles HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "profiles": [
    {
      "name": "code-reviewer",
      "description": "Reviews code for bugs, security issues, and best practices"
    },
    {
      "name": "test-writer",
      "description": "Generates comprehensive unit tests with edge cases"
    },
    {
      "name": "documentation-writer",
      "description": "Creates clear, comprehensive documentation"
    },
    {
      "name": "refactoring-assistant",
      "description": "Suggests refactorings to improve code quality"
    }
  ]
}
```

### Get Profile Details

**Request**:
```http
GET /api/v1/profiles/code-reviewer HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "name": "code-reviewer",
  "description": "Reviews code for bugs, security issues, and best practices",
  "system_prompt": "You are an expert code reviewer with deep knowledge of software engineering best practices, security vulnerabilities, and common pitfalls. When reviewing code:\n\n1. Identify bugs and logical errors\n2. Point out security vulnerabilities\n3. Suggest improvements for readability and maintainability\n4. Recommend best practices\n5. Consider edge cases and error handling\n\nBe constructive and specific in your feedback. Provide code examples when helpful.",
  "allowed_tools": [
    "read",
    "grep",
    "glob"
  ],
  "disallowed_tools": [
    "write",
    "bash",
    "execute"
  ],
  "max_turns": 10,
  "metadata": {
    "category": "code-quality",
    "version": "1.0",
    "author": "amplifier-team"
  }
}
```

### Get Current Profile

**Request**:
```http
GET /api/v1/profiles/current HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "name": "code-reviewer",
  "description": "Reviews code for bugs, security issues, and best practices",
  "system_prompt": "You are an expert code reviewer...",
  "allowed_tools": ["read", "grep", "glob"],
  "disallowed_tools": ["write", "bash", "execute"],
  "max_turns": 10,
  "metadata": {
    "category": "code-quality"
  }
}
```

### Set Current Profile

**Request**:
```http
PUT /api/v1/profiles/current HTTP/1.1
Content-Type: application/json

{
  "profile_name": "test-writer"
}
```

**Response (200 OK)**:
```json
{
  "name": "test-writer",
  "description": "Generates comprehensive unit tests with edge cases",
  "system_prompt": "You are an expert test engineer...",
  "allowed_tools": ["read", "write", "grep"],
  "disallowed_tools": ["bash", "execute"],
  "max_turns": 5,
  "metadata": {
    "category": "testing"
  }
}
```

## Execution Operations

### Single-Shot Execution

**Request**:
```http
POST /api/v1/execute HTTP/1.1
Content-Type: application/json

{
  "prompt": "Explain the difference between mocking and stubbing in unit tests",
  "profile": "test-writer",
  "stream": false
}
```

**Response (200 OK)**:
```json
{
  "content": "Great question! Here's the difference:\n\n**Mocking**:\n- Creates a test double that records interactions\n- Verifies that specific methods were called\n- Asserts on behavior (\"did this method get called with these arguments?\")\n\nExample:\n```python\nfrom unittest.mock import Mock\n\n# Mock records calls\napi_client = Mock()\napi_client.get_user(user_id=123)\n\n# Verify it was called correctly\napi_client.get_user.assert_called_once_with(user_id=123)\n```\n\n**Stubbing**:\n- Creates a test double that returns predefined values\n- Provides canned responses to method calls\n- Focuses on state, not behavior\n\nExample:\n```python\nfrom unittest.mock import Mock\n\n# Stub returns fixed value\napi_client = Mock()\napi_client.get_user.return_value = {\"id\": 123, \"name\": \"Alice\"}\n\n# Use the stub\nresult = api_client.get_user(user_id=123)\nassert result[\"name\"] == \"Alice\"\n```\n\n**Key Difference**:\n- **Mocking** = Verifying interactions (\"was this called?\")\n- **Stubbing** = Providing data (\"return this value\")\n\nOften used together:\n```python\n# Stub the return value\napi_client.get_user.return_value = {\"id\": 123}\n\n# Use it\nservice.process_user(api_client, user_id=123)\n\n# Mock verification\napi_client.get_user.assert_called_once()\n```",
  "metadata": {
    "tokens": 520,
    "duration_ms": 19000,
    "cost_usd": 0.0156,
    "model": "claude-3-5-sonnet-20250120"
  }
}
```

### Streaming Execution (SSE)

**Request**:
```http
POST /api/v1/execute/stream HTTP/1.1
Content-Type: application/json

{
  "prompt": "Write a comprehensive test suite for a user authentication service",
  "profile": "test-writer"
}
```

**Response (200 OK, text/event-stream)**:
```
event: message
data: {"content": "I'll create a comprehensive test suite for user authentication. Let's start with the basic structure:\n\n"}

event: message
data: {"content": "```python\nimport pytest\nfrom unittest.mock import Mock, patch\nfrom auth_service import AuthService\n\n"}

event: message
data: {"content": "class TestAuthService:\n    @pytest.fixture\n    def auth_service(self):\n        return AuthService()\n\n"}

event: message
data: {"content": "    def test_login_success(self, auth_service):\n        \"\"\"Test successful login with valid credentials.\"\"\"\n        result = auth_service.login('user@example.com', 'correct_password')\n        assert result.success is True\n        assert result.user_id is not None\n"}

event: metadata
data: {"tokens": 180, "duration_ms": 8500}

event: message
data: {"content": "\n    def test_login_invalid_email(self, auth_service):\n        \"\"\"Test login fails with invalid email format.\"\"\"\n        result = auth_service.login('invalid-email', 'password')\n        assert result.success is False\n        assert result.error == 'INVALID_EMAIL'\n"}

event: done
data: {"status": "completed", "tokens": 650, "duration_ms": 24000, "cost_usd": 0.0195}
```

## Configuration Operations

### Get Configuration

**Request**:
```http
GET /api/v1/config HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "default_agent": "code-reviewer",
  "retry_attempts": 3,
  "environment": {
    "working_directory": "/home/user/projects/myapp",
    "session_directory": "/home/user/.ccsdk/sessions",
    "log_directory": "/home/user/.ccsdk/logs",
    "cache_directory": "/home/user/.ccsdk/cache",
    "debug": false
  }
}
```

### Update Configuration

**Request**:
```http
PUT /api/v1/config HTTP/1.1
Content-Type: application/json

{
  "retry_attempts": 5,
  "debug": true
}
```

**Response (200 OK)**:
```json
{
  "default_agent": "code-reviewer",
  "retry_attempts": 5,
  "environment": {
    "working_directory": "/home/user/projects/myapp",
    "session_directory": "/home/user/.ccsdk/sessions",
    "log_directory": "/home/user/.ccsdk/logs",
    "cache_directory": "/home/user/.ccsdk/cache",
    "debug": true
  }
}
```

### List Modules

**Request**:
```http
GET /api/v1/config/modules HTTP/1.1
```

**Response (200 OK)**:
```json
{
  "modules": [
    {
      "name": "core",
      "description": "Core amplifier functionality",
      "version": "1.0.0"
    },
    {
      "name": "ccsdk_toolkit",
      "description": "Claude Code SDK integration",
      "version": "1.0.0"
    },
    {
      "name": "scenarios",
      "description": "Pre-built scenario templates",
      "version": "1.0.0"
    }
  ]
}
```

### List Providers

**Request**:
```http
GET /api/v1/config/providers HTTP/1.1
```

**Response (200 OK)**:
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
    },
    {
      "name": "azure-openai",
      "type": "azure",
      "available": false
    }
  ]
}
```

## Error Examples

### Invalid Request (400)

**Request**:
```http
POST /api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/execute HTTP/1.1
Content-Type: application/json

{
  "stream": false
}
```

**Response (400 Bad Request)**:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field 'prompt'",
    "details": {
      "field": "prompt",
      "required": true
    }
  }
}
```

### Session Not Found (404)

**Request**:
```http
GET /api/v1/sessions/00000000-0000-0000-0000-000000000000 HTTP/1.1
```

**Response (404 Not Found)**:
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session not found",
    "details": {
      "session_id": "00000000-0000-0000-0000-000000000000"
    }
  }
}
```

### Profile Not Found (404)

**Request**:
```http
GET /api/v1/profiles/nonexistent-profile HTTP/1.1
```

**Response (404 Not Found)**:
```json
{
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "Profile 'nonexistent-profile' not found",
    "details": {
      "profile_name": "nonexistent-profile",
      "available_profiles": [
        "code-reviewer",
        "test-writer",
        "documentation-writer"
      ]
    }
  }
}
```

### Execution Failed (500)

**Request**:
```http
POST /api/v1/execute HTTP/1.1
Content-Type: application/json

{
  "prompt": "Review this code",
  "profile": "code-reviewer"
}
```

**Response (500 Internal Server Error)**:
```json
{
  "error": {
    "code": "EXECUTION_FAILED",
    "message": "Failed to execute prompt after 3 retries",
    "details": {
      "cause": "SDK connection timeout",
      "retries": 3,
      "last_error": "Connection to Claude API timed out after 30 seconds"
    }
  }
}
```

### Invalid Configuration (400)

**Request**:
```http
PUT /api/v1/config HTTP/1.1
Content-Type: application/json

{
  "retry_attempts": 15
}
```

**Response (400 Bad Request)**:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid configuration value",
    "details": {
      "field": "retry_attempts",
      "value": 15,
      "valid_range": "1-10"
    }
  }
}
```

## Streaming Examples

### JavaScript (Browser)

```javascript
// Create event source for session stream
const sessionId = '550e8400-e29b-41d4-a716-446655440000';
const eventSource = new EventSource(
  `http://localhost:8080/api/v1/sessions/${sessionId}/stream`
);

// Handle message events
eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Content chunk:', data.content);
  
  // Append to UI
  document.getElementById('response').textContent += data.content;
});

// Handle metadata events
eventSource.addEventListener('metadata', (event) => {
  const data = JSON.parse(event.data);
  console.log('Metadata:', data);
  
  // Update stats
  document.getElementById('tokens').textContent = data.tokens;
  document.getElementById('duration').textContent = data.duration_ms;
});

// Handle completion
eventSource.addEventListener('done', (event) => {
  const data = JSON.parse(event.data);
  console.log('Completed:', data);
  
  // Close connection
  eventSource.close();
  
  // Update UI
  document.getElementById('status').textContent = 'Completed';
});

// Handle errors
eventSource.addEventListener('error', (event) => {
  console.error('Stream error:', event);
  
  // Attempt reconnection or show error
  if (event.target.readyState === EventSource.CLOSED) {
    console.log('Connection closed');
    eventSource.close();
  }
});
```

### Python (requests)

```python
import requests
import json

def stream_execution(prompt: str, profile: str = None):
    """Stream execution with SSE."""
    url = 'http://localhost:8080/api/v1/execute/stream'
    
    payload = {'prompt': prompt}
    if profile:
        payload['profile'] = profile
    
    # Start streaming request
    response = requests.post(
        url,
        json=payload,
        stream=True,
        headers={'Accept': 'text/event-stream'}
    )
    
    # Process stream
    event_type = None
    for line in response.iter_lines():
        if not line:
            continue
            
        line = line.decode('utf-8')
        
        # Parse event type
        if line.startswith('event:'):
            event_type = line.split(':', 1)[1].strip()
        
        # Parse data
        elif line.startswith('data:'):
            data_str = line.split(':', 1)[1].strip()
            data = json.loads(data_str)
            
            if event_type == 'message':
                # Print content as it arrives
                print(data['content'], end='', flush=True)
            
            elif event_type == 'metadata':
                print(f"\n[Metadata: {data['tokens']} tokens, "
                      f"{data['duration_ms']}ms]")
            
            elif event_type == 'done':
                print(f"\n[Completed: {data['status']}]")
                break
            
            elif event_type == 'error':
                print(f"\n[Error: {data['message']}]")
                break

# Usage
stream_execution(
    "Write a comprehensive test suite for authentication",
    profile="test-writer"
)
```

### Python (sseclient-py)

```python
import sseclient
import requests
import json

def stream_session_execution(session_id: str, prompt: str):
    """Stream execution in an existing session."""
    # First, execute the prompt (non-blocking)
    requests.post(
        f'http://localhost:8080/api/v1/sessions/{session_id}/execute',
        json={'prompt': prompt, 'stream': False}
    )
    
    # Then connect to SSE stream
    url = f'http://localhost:8080/api/v1/sessions/{session_id}/stream'
    response = requests.get(url, stream=True)
    client = sseclient.SSEClient(response)
    
    for event in client.events():
        data = json.loads(event.data)
        
        if event.event == 'message':
            print(data['content'], end='', flush=True)
        
        elif event.event == 'metadata':
            print(f"\n[{data['tokens']} tokens in {data['duration_ms']}ms]")
        
        elif event.event == 'done':
            print(f"\n[Completed]")
            break
        
        elif event.event == 'error':
            print(f"\n[Error: {data['message']}]")
            break

# Usage
session_id = '550e8400-e29b-41d4-a716-446655440000'
stream_session_execution(session_id, "What about edge cases?")
```

### cURL

```bash
# Stream execution
curl -X POST http://localhost:8080/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{
    "prompt": "Explain test-driven development",
    "profile": "test-writer"
  }'

# Output:
# event: message
# data: {"content": "Test-Driven Development (TDD) is..."}
#
# event: message
# data: {"content": " a software development approach..."}
#
# event: done
# data: {"status": "completed", "tokens": 420}
```
