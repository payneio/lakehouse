# Amplifier Daemon API Documentation

Complete REST API specification and documentation for the Amplifier daemon.

## Documentation Structure

### 📋 [QUICKREF.md](QUICKREF.md) - Start Here
**One-page quick reference for common operations**
- Common workflows (create session, execute, stream)
- All endpoints at a glance
- Request/response formats
- Code examples (Python, JavaScript, cURL)
- Configuration and testing tips

👉 **Use this for**: Quick lookups, copy-paste examples, daily reference

---

### 📖 [README.md](README.md) - Complete Guide
**Comprehensive API documentation**
- Overview and architecture
- All endpoints with detailed descriptions
- Error handling patterns
- SSE streaming guide
- Best practices and patterns
- File storage details
- Development and debugging

👉 **Use this for**: Understanding the API, implementation guidance, best practices

---

### 💡 [EXAMPLES.md](EXAMPLES.md) - Real Examples
**Comprehensive request/response examples for every endpoint**
- Complete request/response payloads
- Error examples with all error codes
- Streaming examples (SSE)
- Multi-language client examples (Python, JavaScript, cURL)
- Edge cases and error scenarios

👉 **Use this for**: Implementing clients, testing, debugging, learning by example

---

### 📜 [CONTRACT.md](CONTRACT.md) - The Formal Contract
**Formal API contract specification**
- Contract philosophy (bricks & studs)
- All endpoints summary
- Data models (TypeScript definitions)
- HTTP status codes and error codes
- SSE event contract
- Versioning strategy
- Breaking vs non-breaking changes
- Contract compliance requirements

👉 **Use this for**: Understanding guarantees, building clients, API evolution decisions

---

### ⚙️ [openapi.yaml](openapi.yaml) - Machine-Readable Spec
**Complete OpenAPI 3.1.0 specification**
- All endpoints with request/response schemas
- Error response definitions
- SSE endpoint specifications
- Server definitions
- Tag organization

👉 **Use this for**: Code generation, API tools, validation, testing

---

## Quick Navigation

### By Use Case

**I want to...**

- **Get started quickly** → [QUICKREF.md](QUICKREF.md)
- **Learn the API thoroughly** → [README.md](README.md)
- **See real examples** → [EXAMPLES.md](EXAMPLES.md)
- **Understand the contract** → [CONTRACT.md](CONTRACT.md)
- **Generate client code** → [openapi.yaml](openapi.yaml)
- **Integrate with my app** → Start with [QUICKREF.md](QUICKREF.md), then [EXAMPLES.md](EXAMPLES.md)
- **Build a client library** → [CONTRACT.md](CONTRACT.md) + [openapi.yaml](openapi.yaml)
- **Debug an issue** → [EXAMPLES.md](EXAMPLES.md) error section
- **Understand versioning** → [CONTRACT.md](CONTRACT.md) versioning section
- **Contribute to API** → [CONTRACT.md](CONTRACT.md) + contract tests

### By Resource

**Sessions**:
- Quick reference: [QUICKREF.md#sessions](QUICKREF.md)
- Full docs: [README.md#session-operations](README.md)
- Examples: [EXAMPLES.md#session-operations](EXAMPLES.md)
- Contract: [CONTRACT.md#sessions](CONTRACT.md)

**Profiles**:
- Quick reference: [QUICKREF.md#profiles](QUICKREF.md)
- Full docs: [README.md#profile-operations](README.md)
- Examples: [EXAMPLES.md#profile-operations](EXAMPLES.md)
- Contract: [CONTRACT.md#profiles](CONTRACT.md)

**Execution**:
- Quick reference: [QUICKREF.md#execution](QUICKREF.md)
- Full docs: [README.md#execution-operations](README.md)
- Examples: [EXAMPLES.md#execution-operations](EXAMPLES.md)
- Contract: [CONTRACT.md#execution](CONTRACT.md)

**Streaming (SSE)**:
- Quick reference: [QUICKREF.md#sse-events](QUICKREF.md)
- Full docs: [README.md#streaming-sse](README.md)
- Examples: [EXAMPLES.md#streaming-examples](EXAMPLES.md)
- Contract: [CONTRACT.md#sse-contract](CONTRACT.md)

**Errors**:
- Quick reference: [QUICKREF.md#error-codes](QUICKREF.md)
- Full docs: [README.md#error-handling](README.md)
- Examples: [EXAMPLES.md#error-examples](EXAMPLES.md)
- Contract: [CONTRACT.md#standard-error-codes](CONTRACT.md)

## Key Concepts

### What is this API?

The Amplifier Daemon API exposes amplifier CLI functionality as HTTP endpoints, enabling:
- Persistent conversation sessions with Claude
- Profile-based agent configurations
- Single-shot and streaming LLM interactions
- Session management and history

### Core Resources

1. **Session**: A persistent conversation context
2. **Profile**: An agent configuration (system prompt + tools)
3. **Execution**: LLM interaction (single-shot or streaming)
4. **Configuration**: Daemon settings

### Architecture Principles

Following the "bricks and studs" philosophy:
- **Contract-first**: OpenAPI spec drives implementation
- **Regeneratable**: Implementation can be rebuilt from contract
- **Minimal & clear**: Only essential endpoints
- **File-based persistence**: Simple, debuggable JSON storage
- **SSE for streaming**: Real-time progress updates

## API Overview

### Base URL
```
http://localhost:8080/api/v1
```

### Endpoint Count: 17 endpoints total

- Status: 2
- Sessions: 5
- Profiles: 4
- Execution: 2
- Configuration: 4

### Common Operations

**Create & use a session**:
```bash
# 1. Create
SESSION_ID=$(curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "my-session"}' \
  | jq -r '.metadata.session_id')

# 2. Execute
curl -X POST "http://localhost:8080/api/v1/sessions/$SESSION_ID/execute" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Review this code"}'
```

**Single-shot execution**:
```bash
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain TDD"}'
```

**Streaming execution**:
```bash
curl -X POST http://localhost:8080/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -N \
  -d '{"prompt": "Write comprehensive tests"}'
```

## Client Libraries

### Python

```python
import requests

# Basic usage
resp = requests.post(
    'http://localhost:8080/api/v1/execute',
    json={'prompt': 'Explain mocking'}
)
print(resp.json()['content'])
```

See [EXAMPLES.md](EXAMPLES.md) for complete Python examples.

### JavaScript

```javascript
// Basic usage
const resp = await fetch('http://localhost:8080/api/v1/execute', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({prompt: 'Explain mocking'})
});
const {content} = await resp.json();
console.log(content);
```

See [EXAMPLES.md](EXAMPLES.md) for complete JavaScript examples.

## Testing

### Health Check
```bash
curl http://localhost:8080/api/v1/health
```

### Contract Tests
```bash
pytest tests/api/contract/ -v
```

### Viewing OpenAPI Spec
```bash
swagger-ui lakehoused/api/openapi.yaml
```

## Version Information

- **Current Version**: v1
- **API Path**: `/api/v1/...`
- **OpenAPI Version**: 3.1.0
- **Stability**: v1 guarantees no breaking changes

## Support & Contributing

- **Issues**: Report bugs or request features
- **Discussions**: Ask questions, share ideas
- **Contract Tests**: All changes must pass contract tests
- **Breaking Changes**: Require v2, documented in [CONTRACT.md](CONTRACT.md)

## File Manifest

```
lakehoused/api/
├── INDEX.md          # This file - documentation index
├── QUICKREF.md       # One-page quick reference
├── README.md         # Complete API documentation
├── EXAMPLES.md       # Request/response examples
├── CONTRACT.md       # Formal API contract
└── openapi.yaml      # OpenAPI 3.1.0 specification
```

## Related Documentation

- **Amplifier CLI**: `../cli/README.md`
- **Session Management**: `../sessions/README.md`
- **Profile Configuration**: `../profiles/README.md`
- **CCSDK Toolkit**: `../../amplifier/ccsdk_toolkit/README.md`

---

**Last Updated**: 2025-11-20  
**API Version**: 1.0.0  
**OpenAPI Version**: 3.1.0
