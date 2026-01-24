# Amplifier Daemon API Contract

**Version**: 1.0.0  
**Base URL**: `http://localhost:8080/api/v1`

This document defines the complete API contract for the Amplifier daemon following the "bricks and studs" philosophy - the contract is the stable interface that consumers depend on.

## Contract Philosophy

### The Studs (Connection Points)

The API contract defines:
- **Endpoint paths**: Fixed URLs that won't change within v1
- **Request schemas**: What data consumers send
- **Response schemas**: What data consumers receive
- **Error formats**: Standard error responses
- **Status codes**: HTTP semantics

### The Bricks (Implementation)

The implementation:
- Can be regenerated from this contract
- May change internally without breaking consumers
- Must always satisfy the contract
- Is tested against contract compliance

### Regeneratability

This API is designed to be regeneratable:
1. Contract specifies behavior precisely
2. Implementation can be rebuilt from scratch
3. Tests verify contract compliance
4. Consumers never break

## Quick Reference

### Core Resources

| Resource | Purpose | Key Endpoints |
|----------|---------|---------------|
| **Sessions** | Persistent conversation contexts | `POST /sessions`, `POST /sessions/{id}/execute` |
| **Profiles** | Agent configurations | `GET /profiles`, `PUT /profiles/current` |
| **Execute** | Single-shot operations | `POST /execute`, `POST /execute/stream` |
| **Config** | Daemon configuration | `GET /config`, `PUT /config` |

### Streaming Endpoints

| Endpoint | Type | Purpose |
|----------|------|---------|
| `GET /sessions/{id}/stream` | SSE | Real-time session updates |
| `POST /execute/stream` | SSE | Streaming single-shot execution |

## Endpoint Summary

### Status (2 endpoints)

```
GET  /health                  -> Health check
GET  /status                  -> Detailed daemon status
```

### Sessions (5 endpoints)

```
GET    /sessions              -> List sessions
POST   /sessions              -> Create session
GET    /sessions/{id}         -> Get session details
DELETE /sessions/{id}         -> Delete session
POST   /sessions/{id}/execute -> Execute in session
GET    /sessions/{id}/stream  -> Stream session events (SSE)
```

### Profiles (4 endpoints)

```
GET  /profiles              -> List profiles
GET  /profiles/{name}       -> Get profile details
GET  /profiles/current      -> Get current profile
PUT  /profiles/current      -> Set current profile
```

### Execution (2 endpoints)

```
POST /execute        -> Single-shot execution
POST /execute/stream -> Streaming execution (SSE)
```

### Configuration (4 endpoints)

```
GET  /config           -> Get configuration
PUT  /config           -> Update configuration
GET  /config/modules   -> List modules
GET  /config/providers -> List providers
```

## Request/Response Contract

### Standard Response Format

All JSON responses follow this structure:

**Success (2xx)**:
```json
{
  "<resource>": { ... },
  "metadata": { ... }
}
```

**Error (4xx/5xx)**:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... }
  }
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PUT |
| 201 | Created | Successful POST creating resource |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request data |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Error | Server-side failure |

### Standard Error Codes

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `INVALID_REQUEST` | 400 | Missing/invalid fields |
| `NOT_FOUND` | 404 | Resource not found |
| `SESSION_NOT_FOUND` | 404 | Session ID invalid |
| `PROFILE_NOT_FOUND` | 404 | Profile name invalid |
| `EXECUTION_FAILED` | 500 | LLM execution failed |
| `INTERNAL_ERROR` | 500 | Unexpected error |

## Data Models Contract

### Session

```typescript
interface Session {
  metadata: SessionMetadata;
  messages: Message[];
  context: Record<string, any>;
  config: Record<string, any>;
}

interface SessionMetadata {
  session_id: string;           // UUID
  name: string;
  created_at: string;           // ISO 8601
  updated_at: string;           // ISO 8601
  turns: number;
  total_tokens?: number;
  cost_usd?: number;
  duration_seconds?: number;
  tags: string[];
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;            // ISO 8601
  metadata?: Record<string, any>;
}
```

### Profile

```typescript
interface Profile {
  name: string;
  description?: string;
  system_prompt: string;
  allowed_tools: string[];
  disallowed_tools: string[];
  max_turns: number;
  metadata?: Record<string, any>;
}
```

### Execution

```typescript
interface ExecutionRequest {
  prompt: string;
  profile?: string;
  stream?: boolean;
}

interface ExecutionResponse {
  content: string;
  metadata: {
    tokens?: number;
    duration_ms?: number;
    cost_usd?: number;
    model?: string;
    [key: string]: any;
  };
}
```

### Error

```typescript
interface ErrorResponse {
  error: {
    code: string;              // Machine-readable
    message: string;           // Human-readable
    details: Record<string, any>;
  };
}
```

## SSE Contract

### Event Format

```
event: <event_type>
data: <json_payload>

```

### Event Types

| Event | Payload | Meaning |
|-------|---------|---------|
| `message` | `{"content": "..."}` | Content chunk |
| `metadata` | `{"tokens": N, "duration_ms": N}` | Progress update |
| `error` | `{"code": "...", "message": "..."}` | Error occurred |
| `done` | `{"status": "completed"}` | Execution complete |

### SSE Guarantees

1. Events arrive in order
2. Each event has `event` and `data` fields
3. `data` is always valid JSON
4. Stream ends with `done` or `error` event
5. Connection closes after terminal event

## Versioning Contract

### Current Version: v1

**Version Path**: `/api/v1/...`

**Stability Promise**:
- Additive changes allowed (new endpoints, optional fields)
- No breaking changes (field removal, type changes, semantic changes)
- Deprecation warnings before any removal
- Version stays v1 as long as possible

### When v2 Happens

Version 2 will only be created for:
- Fundamental architecture changes
- Incompatible data model changes
- Breaking semantic changes

**Migration Path**:
1. v2 announced with changelog
2. v1 deprecated but supported
3. Overlap period (6 months minimum)
4. v1 sunset with clear timeline

## Implementation Contract

### File-Based Persistence

**Session Storage**:
- Location: `~/.ccsdk/sessions/`
- Format: JSON files named `{session_id}.json`
- Encoding: UTF-8
- Pretty-printed for debugging

**Guarantees**:
- Sessions persist across daemon restarts
- File writes are atomic (temp file + rename)
- Corrupted files don't crash daemon
- Sessions can be manually edited/backed up

### Concurrency

**Multi-Session Support**:
- Multiple sessions can be active simultaneously
- Session operations are thread-safe
- No global locks (sessions are independent)

**Long-Running Operations**:
- LLM calls are non-blocking
- SSE provides real-time updates
- Timeout after 5 minutes (configurable)

### Resource Limits

**Default Limits**:
- Max concurrent sessions: 10
- Max session size: 10 MB
- Max message length: 100 KB
- Session retention: 30 days

**Configurable**:
- Via config file or `/config` endpoint
- Changes apply immediately (no restart)

## Breaking vs Non-Breaking Changes

### ✅ Non-Breaking (Safe)

- Adding new endpoints
- Adding optional fields to requests
- Adding fields to responses
- Adding new error codes
- Relaxing validation (accepting more)
- Performance improvements
- Internal refactoring

### ❌ Breaking (Require v2)

- Removing endpoints
- Removing request/response fields
- Changing field types
- Changing semantics (same field, different meaning)
- Stricter validation (rejecting what was accepted)
- Changing error code meanings

## Testing Contract Compliance

### Contract Tests

Every implementation must pass:

1. **Endpoint tests**: All endpoints return correct status codes
2. **Schema tests**: Responses match declared schemas
3. **Error tests**: Errors follow standard format
4. **SSE tests**: Events match declared format
5. **Persistence tests**: Sessions survive restart

### Test Suite Location

`tests/api/contract/` contains the authoritative test suite.

**Running tests**:
```bash
pytest tests/api/contract/ -v
```

**CI Requirement**: All contract tests must pass before merge.

## Consumer Guidelines

### Don't Depend On

- Response field order
- Internal implementation details
- Undocumented behavior
- Error message text (use error codes)
- Timing/performance characteristics

### Do Depend On

- Endpoint paths
- Request/response schemas
- Error codes
- HTTP status codes
- SSE event types

### Best Practices

1. **Parse defensively**: Ignore unknown fields
2. **Handle errors by code**: Don't parse error messages
3. **Retry with backoff**: Transient errors happen
4. **Close SSE connections**: Don't leak connections
5. **Validate assumptions**: Test against contract, not implementation

## Evolution Strategy

### Adding Features

**New Endpoint**:
1. Define in OpenAPI spec
2. Add contract tests
3. Implement
4. Document examples
5. Deploy

**New Optional Field**:
1. Update schema
2. Update tests
3. Implement (maintain backward compat)
4. Update docs

### Deprecation Process

1. **Announce**: Document deprecation in changelog
2. **Warn**: Add deprecation headers to responses
3. **Grace Period**: Minimum 6 months
4. **Remove**: Only in next major version

## OpenAPI Specification

The complete, machine-readable contract is defined in:

**File**: `openapi.yaml`  
**Format**: OpenAPI 3.1.0

This specification is the source of truth. All documentation derives from it.

## Documentation

### Complete Documentation

- **README.md**: Overview, quick start, best practices
- **EXAMPLES.md**: Comprehensive request/response examples
- **CONTRACT.md**: This file - the formal contract
- **openapi.yaml**: Machine-readable specification

### Viewing Documentation

**Swagger UI**:
```bash
swagger-ui lakehoused/api/openapi.yaml
```

**Redoc**:
```bash
redoc-cli serve lakehoused/api/openapi.yaml
```

## Contract Compliance Checklist

Before deploying changes:

- [ ] OpenAPI spec updated
- [ ] Contract tests pass
- [ ] Examples updated
- [ ] No breaking changes (or v2 created)
- [ ] Backward compatibility verified
- [ ] Error codes documented
- [ ] SSE events documented (if applicable)

## Summary

This contract defines:

1. **What**: All endpoints, data models, error formats
2. **How**: HTTP methods, status codes, SSE events
3. **Guarantees**: Stability promises, non-breaking changes
4. **Testing**: Contract compliance requirements

**The contract is the product. The implementation is regeneratable.**

Consumers depend on this contract remaining stable within v1. Implementation can change freely as long as the contract is satisfied.
