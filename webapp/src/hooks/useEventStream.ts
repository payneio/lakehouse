import React, { useEffect, useRef, useCallback, useState } from 'react';
import { BASE_URL } from '@/api/client';

type EventHandler = (data: unknown) => void;

interface ExecutionStateHandlers {
  startTurn: (userMessage: string) => void;
  completeTurn: () => void;
  addTool: (toolName: string, toolInput?: Record<string, unknown>, toolCallId?: string) => void;
  updateTool: (toolCallId: string, updates: { status?: string; endTime?: number; result?: unknown; error?: string }) => void;
  addThinking: (content: string) => void;
}

interface UseEventStreamOptions {
  sessionId: string;
  onError?: (error: Error) => void;
  executionHandlers?: ExecutionStateHandlers;
}

interface EventStreamState {
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
  error?: Error;
}

export function useEventStream({ sessionId, onError, executionHandlers }: UseEventStreamOptions) {
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
      return;
    }

    isConnectedRef.current = true;

    const eventSource = new EventSource(
      `${BASE_URL}/api/v1/sessions/${sessionId}/stream`,
      { withCredentials: true }
    );

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
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
        try {
          const parsed = JSON.parse(event.data);

          // Integrate with execution state tracking
          if (executionHandlers) {
            handleExecutionEvent(eventName, parsed);
          }

          emit(eventName, parsed);
        } catch (error) {
          console.error(`Error parsing ${eventName} event:`, error);
        }
      });
    };

    // Handle execution state updates from SSE events
    const handleExecutionEvent = (eventName: string, data: Record<string, unknown>) => {
      if (!executionHandlers) return;

      // Log the full event data for debugging
      console.log('[useEventStream] Event:', eventName, 'Data:', JSON.stringify(data, null, 2));

      switch (eventName) {
        case 'assistant_message_start':
          // Start new turn with last user message
          // Note: We'll need to track the last user message separately
          executionHandlers.startTurn((data.user_message as string) || '');
          break;

        case 'hook:tool:pre': {
          // Log the complete raw event
          console.log('[useEventStream] RAW tool:pre event:', JSON.stringify(data, null, 2));

          // Extract tool data from hook_data wrapper
          const hookData = data.hook_data as Record<string, unknown> | undefined;
          if (!hookData) {
            console.warn('[useEventStream] Missing hook_data in tool:pre event');
            console.log('[useEventStream] Full event data:', data);
            break;
          }

          const tool_name = hookData.tool_name as string;
          const tool_input = hookData.tool_input as Record<string, unknown>;
          const tool_call_id = hookData.tool_call_id as string;

          console.log('[useEventStream] Extracted tool data:', {
            tool_name,
            tool_input,
            tool_call_id,
            hookData_keys: Object.keys(hookData)
          });

          // Add tool to current turn
          executionHandlers.addTool(tool_name, tool_input, tool_call_id);
          break;
        }

        case 'hook:tool:post': {
          // Log the complete raw event
          console.log('[useEventStream] RAW tool:post event:', JSON.stringify(data, null, 2));

          // Extract tool data from hook_data wrapper
          const hookData = data.hook_data as Record<string, unknown> | undefined;
          if (!hookData) {
            console.warn('[useEventStream] Missing hook_data in tool:post event');
            console.log('[useEventStream] Full event data:', data);
            break;
          }

          const tool_call_id = hookData.tool_call_id as string;
          const is_error = hookData.is_error as boolean;
          const tool_result = hookData.tool_result;

          console.log('[useEventStream] Extracted tool completion:', {
            tool_call_id,
            is_error,
            result_preview: typeof tool_result === 'string' ? tool_result.substring(0, 100) : tool_result,
            hookData_keys: Object.keys(hookData)
          });

          // Update tool with completion data
          executionHandlers.updateTool(tool_call_id, {
            status: is_error ? 'error' : 'completed',
            endTime: Date.now(),
            result: tool_result,
            error: is_error ? String(tool_result) : undefined,
          });
          break;
        }

        case 'hook:thinking:delta': {
          // Extract thinking data from hook_data wrapper
          const hookData = data.hook_data as Record<string, unknown> | undefined;
          if (!hookData) {
            console.warn('[useEventStream] Missing hook_data in thinking:delta event');
            break;
          }

          // Add thinking block
          executionHandlers.addThinking(hookData.delta as string);
          break;
        }

        case 'assistant_message_complete':
          // Complete current turn
          executionHandlers.completeTurn();
          break;
      }
    };

    // Register listeners for known named events
    // Message lifecycle events
    addNamedEventListener('user_message_saved');
    addNamedEventListener('assistant_message_start');
    addNamedEventListener('content');
    addNamedEventListener('assistant_message_complete');

    // Hook events
    addNamedEventListener('hook:tool:pre');
    addNamedEventListener('hook:tool:post');
    addNamedEventListener('hook:thinking:delta');
    addNamedEventListener('hook:approval:required');

    // Execution lifecycle events
    addNamedEventListener('execution_cancelled');
    addNamedEventListener('execution_error');

    // Connection events
    addNamedEventListener('keepalive');
    // Note: 'connected' and 'error' are NOT SSE data events - they're handled
    // by onopen and onerror callbacks. EventSource error events don't have
    // event.data, causing JSON parse errors if we try to listen for them.

    return () => {
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
