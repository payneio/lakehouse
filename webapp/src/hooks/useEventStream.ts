import React, { useEffect, useRef, useCallback, useState } from 'react';
import { BASE_URL } from '@/api/client';

type EventHandler = (data: unknown) => void;

interface UseEventStreamOptions {
  sessionId: string;
  onError?: (error: Error) => void;
}

interface EventStreamState {
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
  error?: Error;
}

export function useEventStream({ sessionId, onError }: UseEventStreamOptions) {
  // All hooks at top level - unconditionally
  const handlersRef = useRef<Map<string, Set<EventHandler>>>(new Map());
  const eventSourceRef = useRef<EventSource | null>(null);
  const isConnectedRef = useRef(false);
  const [state, setState] = useState<EventStreamState>({
    status: sessionId ? 'connecting' : 'disconnected'
  });

  const on = useCallback((eventType: string, handler: EventHandler) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set());
    }
    handlersRef.current.get(eventType)!.add(handler);

    return () => {
      handlersRef.current.get(eventType)?.delete(handler);
      if (handlersRef.current.get(eventType)?.size === 0) {
        handlersRef.current.delete(eventType);
      }
    };
  }, []);

  const emit = useCallback((eventType: string, data: unknown) => {
    const handlers = handlersRef.current.get(eventType);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in event handler for ${eventType}:`, error);
        }
      });
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    // Prevent duplicate connections (especially from React StrictMode double-mounting)
    if (eventSourceRef.current && eventSourceRef.current.readyState !== EventSource.CLOSED) {
      console.log('[useEventStream] Connection already exists, skipping');
      return;
    }

    console.log('[useEventStream] Creating new connection for:', sessionId);
    isConnectedRef.current = true;

    const eventSource = new EventSource(
      `${BASE_URL}/api/v1/sessions/${sessionId}/stream`,
      { withCredentials: true }
    );

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('[useEventStream] Connection opened for:', sessionId);
      setState({ status: 'connected' });
      emit('connected', {});
    };

    eventSource.onerror = () => {
      const err = new Error('SSE connection error');
      setState({ status: 'error', error: err });
      emit('error', { error: err.message });
      onError?.(err);
    };

    // Handle named events by adding listeners for specific event types
    const addNamedEventListener = (eventName: string) => {
      eventSource.addEventListener(eventName, (event) => {
        console.log(`[useEventStream] Received raw event "${eventName}":`, event.data);
        try {
          const parsed = JSON.parse(event.data);
          console.log(`[useEventStream] Parsed event "${eventName}":`, parsed);
          console.log(`[useEventStream] Emitting to ${handlersRef.current.get(eventName)?.size || 0} handlers`);
          emit(eventName, parsed);
        } catch (error) {
          console.error(`Error parsing ${eventName} event:`, error);
        }
      });
    };

    // Register listeners for known named events
    // Message lifecycle events
    console.log('[useEventStream] Registering event listeners...');
    addNamedEventListener('user_message_saved');
    addNamedEventListener('assistant_message_start');
    addNamedEventListener('content');
    addNamedEventListener('assistant_message_complete');
    console.log('[useEventStream] Registered message lifecycle listeners');

    // Hook events
    addNamedEventListener('hook:tool:pre');
    addNamedEventListener('hook:tool:post');
    addNamedEventListener('hook:thinking:delta');
    addNamedEventListener('hook:approval:required');

    // Connection events
    addNamedEventListener('keepalive');
    // Note: 'connected' and 'error' are NOT SSE data events - they're handled
    // by onopen and onerror callbacks. EventSource error events don't have
    // event.data, causing JSON parse errors if we try to listen for them.

    // Add generic message handler to catch any unhandled events (debugging)
    eventSource.onmessage = (event) => {
      console.log('[useEventStream] GENERIC onmessage fired (event without explicit type):', event);
      console.log('[useEventStream] Event type:', event.type);
      console.log('[useEventStream] Event data:', event.data);
    };

    return () => {
      console.log('[useEventStream] Cleanup called, closing connection');
      eventSource.close();
      eventSourceRef.current = null;
      isConnectedRef.current = false;
      emit('disconnected', {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]); // emit and onError omitted intentionally - they're stable via useCallback

  // Return stable object to prevent unnecessary re-renders in consuming components
  return React.useMemo(() => ({ on, emit, state }), [on, emit, state]);
}
