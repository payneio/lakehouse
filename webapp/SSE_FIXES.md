# SSE Implementation Fixes

**Date**: 2025-11-30
**Status**: ✅ Fixed

## Issues Fixed

### Issue 1: JSON Parse Error on 'error' Event ❌→✅

**Problem**: EventSource `onerror` events don't have `event.data` - trying to parse undefined as JSON
```
Error parsing error event: SyntaxError: "undefined" is not valid JSON
```

**Root Cause**: Lines 103-104 in `useEventStream.ts` registered named event listeners for 'connected' and 'error', which are connection lifecycle events, NOT SSE data events. These events are already handled by `onopen` and `onerror` callbacks.

**Fix**: Removed lines registering listeners for 'connected' and 'error' events:
```typescript
// REMOVED:
addNamedEventListener('connected');
addNamedEventListener('error');
```

**Location**: `webapp/src/hooks/useEventStream.ts:103-104`

---

### Issue 2: Infinite Loop in SessionView ❌→✅

**Problem**: Maximum update depth exceeded error
```
SessionView.tsx:71  Maximum update depth exceeded
setLocalMessages(transcript)
```

**Root Cause**: The effect at line 68-73 runs whenever `transcript` changes. If React Query returns a new array instance on every render (even with same contents), this creates an infinite loop:
```typescript
React.useEffect(() => {
  if (transcript) {
    setLocalMessages(transcript); // Triggers re-render
  }
}, [transcript]); // New transcript array → run effect → setState → re-render → repeat
```

**Fix**: Added a `useRef` to track initialization state, preventing re-initialization on subsequent renders:
```typescript
const transcriptInitialized = React.useRef(false);

React.useEffect(() => {
  if (transcript && !transcriptInitialized.current) {
    setLocalMessages(transcript);
    transcriptInitialized.current = true;
  }
}, [transcript]);

// Reset when sessionId changes
React.useEffect(() => {
  transcriptInitialized.current = false;
  setLocalMessages([]);
}, [sessionId]);
```

**Location**: `webapp/src/features/session/components/SessionView.tsx:68-83`

---

### Issue 3: Dependency Documentation Improvement ✅

**Problem**: The SSE event handler effect at line 77 has a comment that could be clearer about WHY it only depends on `sessionId` and `eventStream.on`.

**Fix**: Enhanced comment to explain the stability contract:
```typescript
// Wire up SSE event handlers
// Note: Only depend on sessionId and stable 'on' function (from useCallback),
// not the full eventStream object which changes on every state update
React.useEffect(() => {
  // ...
}, [sessionId, eventStream.on]);
```

**Location**: `webapp/src/features/session/components/SessionView.tsx:85-87`

---

## Testing Verification Steps

1. **JSON Parse Error**: Fixed by removing invalid event listeners
   - ✅ No more "undefined is not valid JSON" errors
   - ✅ Connection errors handled by `onerror` callback only
   - ✅ Named events (keepalive, etc.) still work correctly

2. **Infinite Loop**: Fixed by ref-based initialization guard
   - ✅ No more "Maximum update depth exceeded" errors
   - ✅ Transcript initializes once per session
   - ✅ Resets properly when switching sessions

3. **SSE Event Handling**: Still works correctly
   - ✅ user_message_saved events received
   - ✅ assistant_message_start events received
   - ✅ content streaming events received
   - ✅ assistant_message_complete events received
   - ✅ Hook events (tool:pre, tool:post, etc.) received

## Technical Details

### EventSource Event Types

There are two categories of events in EventSource:

1. **Connection Lifecycle Events** (handled by callbacks):
   - `onopen` - Connection established
   - `onerror` - Connection error (NO event.data)
   - Manual `close()` - Connection closed

2. **SSE Data Events** (have event.data):
   - Named events: `event: user_message_saved\ndata: {...}`
   - Default events: Just `data: {...}` (no event field)

The bug was treating connection lifecycle events as SSE data events.

### React Effect Dependencies

The `eventStream` object from `useEventStream` returns:
```typescript
{ on, emit, state }
```

Where:
- `on` - Stable (useCallback with no deps)
- `emit` - Stable (useCallback with no deps)
- `state` - **Changes on every setState call**

Because `state` changes frequently, the memoized return value changes, which would cause effects depending on `eventStream` to re-run constantly. The fix is to only depend on the stable parts (`on`, `emit`) or specific properties.

## Files Modified

1. `webapp/src/hooks/useEventStream.ts`
   - Removed invalid event listeners (lines 103-104)
   - Added clarifying comment

2. `webapp/src/features/session/components/SessionView.tsx`
   - Added ref-based initialization guard (lines 70-83)
   - Enhanced dependency comment (lines 85-87)

## Pre-existing Issues (Not Fixed)

The following issues existed before and were not addressed:

1. Backend test failures (5 failed tests in daemon/test_api_execute.py)
2. TypeScript errors in other files (DirectoryDetailsPanel, ApprovalDialog, ToolCallDisplay)

These are unrelated to the SSE fixes and should be addressed separately.
