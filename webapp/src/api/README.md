# API Client Module

HTTP client for lakehoused REST API.

## Purpose

Provides typed access to all lakehoused API endpoints with proper error handling.

## Contract

**Inputs:** Endpoint path, request options
**Outputs:** Typed JSON responses
**Side Effects:** Network requests
**Dependencies:** fetch API, environment variables

## Usage

```typescript
import { listBundles, createSession } from '@/api';

const bundles = await listBundles();
const session = await createSession({ bundle_name: 'default' });
```

## Environment Variables

- `VITE_API_URL` - Base URL for API (default: `http://localhost:8000`)

## Modules

### `client.ts`
Base HTTP client with error handling.

- `fetchApi<T>()` - Generic fetch wrapper with JSON parsing and error handling
- `ApiError` - Custom error class with status codes

### `collections.ts`
Collection management endpoints.

- `listCollections()` - Get all collections
- `getCollection(identifier)` - Get collection by identifier
- `syncCollections(params)` - Sync collections from registry

### `bundles.ts`
Bundle listing endpoints.

- `listBundles()` - Get all available bundles

### `projects.ts`
Project management endpoints.

- `listProjects()` - Get all projects
- `getProject(relativePath)` - Get project by path
- `createProject(data)` - Create new project
- `updateProject(relativePath, data)` - Update project
- `deleteProject(relativePath, removeMarker)` - Delete project

### `sessions.ts`
Session management endpoints.

- `listSessions(params)` - Get sessions with optional filters
- `getSession(sessionId)` - Get session by ID
- `createSession(data)` - Create new session
- `startSession(sessionId)` - Start session execution
- `deleteSession(sessionId)` - Delete session
- `getTranscript(sessionId, limit)` - Get session transcript
- `sendMessage(sessionId, content, role)` - Send message to session

### `sse.ts`
Server-Sent Events utilities.

- `createSSEConnection(endpoint, handlers)` - Create SSE connection with cleanup
- `executeSessionWithStream(sessionId, content)` - Execute session with SSE streaming
  - **Note:** SSE POST not fully implemented - needs custom handling

## Error Handling

All API functions throw `ApiError` on HTTP errors:

```typescript
try {
  const data = await listCollections();
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API error ${error.status}: ${error.message}`);
  }
}
```

## Type Safety

All API responses are fully typed. See `src/types/api.ts` for type definitions.

## Testing

The API client is a self-contained module with clear contracts. To test:

1. Start lakehoused backend: `cd lakehoused && uv run uvicorn lakehoused.main:app`
2. Import and call functions from your components
3. All network errors will be properly typed and caught

## Future Improvements

- [ ] Implement custom SSE POST handling for session execution streaming
- [ ] Add request cancellation support
- [ ] Add request retry logic
- [ ] Add request/response logging in development mode
