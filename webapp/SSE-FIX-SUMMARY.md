# SSE Connection and Event Handler Fixes

## Issues Fixed

### 1. Multiple /stream Connections (FIXED)
**Problem**: 3 EventSource connections showing in Network tab instead of 1
**Root Cause**:
- SessionView created useEventStream → Connection #1
- ToolCallDisplay created useEventStream → Connection #2 (DUPLICATE!)
- React StrictMode double-mounting multiplied the connections

**Fix**:
- Removed duplicate `useEventStream` call from ToolCallDisplay
- Now ToolCallDisplay receives `eventStream` as prop from SessionView
- Result: Only ONE /stream connection per session ✓

### 2. Event Handlers Not Firing (FIXED)
**Problem**: No console logs despite events arriving
**Root Cause**:
```typescript
useEffect(() => {
  return eventStream.on('hook:tool:pre', ...);
}, [eventStream]);  // ← eventStream changes every render!
```
- `eventStream` in dependencies caused re-run on every render
- useEffect immediately called unsubscribe function
- Handler never stayed registered long enough

**Fix**:
```typescript
useEffect(() => {
  const unsubPre = eventStream.on('hook:tool:pre', ...);
  const unsubPost = eventStream.on('hook:tool:post', ...);
  return () => {
    unsubPre();
    unsubPost();
  };
}, [sessionId, eventStream.on]);  // Only depend on stable function
```

### 3. Debug Logging Added (ENHANCED)
**Added comprehensive logging to track event flow**:
- `useEventStream.ts`: Logs raw events, parsed events, handler counts
- `ToolCallDisplay.tsx`: Logs when handlers are set up and when events arrive
- `SessionView.tsx`: Already had good logging

## Files Changed

1. **ToolCallDisplay.tsx** (`src/features/session/components/`)
   - Removed duplicate `useEventStream()` call
   - Added `eventStream` prop to receive from parent
   - Added proper TypeScript interface `HookEventData`
   - Fixed useEffect dependencies
   - Added debug logging

2. **SessionView.tsx** (`src/features/session/components/`)
   - Passes `eventStream` prop to ToolCallDisplay

3. **useEventStream.ts** (`src/hooks/`)
   - Added debug logging in `addNamedEventListener`
   - Shows: raw event data, parsed data, handler count

## Expected Behavior

**Network Tab**: Should show only ONE `/stream` connection per session
**Console**: Should show event flow:
```
[useEventStream] Received raw event "hook:tool:pre": {...}
[useEventStream] Parsed event "hook:tool:pre": {...}
[useEventStream] Emitting to 1 handlers
[ToolCallDisplay] hook:tool:pre received: {...}
```

**UI**: Tool call display should show when tools are called

## Testing

To verify the fix:
1. Open session view
2. Open browser DevTools → Network tab
3. Filter for "stream"
4. Should see only ONE EventSource connection (not 3)
5. Open Console tab
6. Send a message that triggers tool calls
7. Should see event logs flowing through
8. UI should show tool call status

## Technical Notes

- EventStream sharing prevents duplicate connections
- Stable dependencies prevent premature unsubscription
- Debug logging helps diagnose event flow issues
- Pattern matches SessionView's working implementation
