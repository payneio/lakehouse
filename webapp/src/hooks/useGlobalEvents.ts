import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BASE_URL } from '@/api/client';

/**
 * Global event stream hook that subscribes to system-wide events.
 * This should be used at the app root to handle global state updates.
 *
 * Handles:
 * - session:created - Invalidates sessions list and unread counts
 * - session:updated - Updates cached session data and unread counts
 *
 * Also handles mobile app backgrounding gracefully - pauses SSE when hidden
 * and reconnects when visible without triggering page reloads.
 */
export function useGlobalEvents() {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  const wasHiddenRef = useRef(false);

  useEffect(() => {
    function createEventSource() {
      const eventSource = new EventSource(`${BASE_URL}/api/v1/events`);
      eventSourceRef.current = eventSource;
      return eventSource;
    }

    function attachEventListeners(es: EventSource) {
      es.addEventListener('session:created', (e) => {
        const event = JSON.parse(e.data);
        queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
        queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
      });

      es.addEventListener('session:updated', (e) => {
        const event = JSON.parse(e.data);
        if (event.fields_changed?.includes('is_unread')) {
          queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
          queryClient.invalidateQueries({ queryKey: ['session', event.session_id] });
          queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
        }
      });

      es.addEventListener('keepalive', () => {
        // Silent keepalive
      });

      es.onerror = (error) => {
        console.error('[useGlobalEvents] Event stream error:', error);
      };
    }

    let eventSource = createEventSource();
    attachEventListeners(eventSource);

    // Handle visibility changes for mobile app backgrounding
    // When app is hidden, close SSE to save resources
    // When app becomes visible again, reconnect without full page reload
    function handleVisibilityChange() {
      if (document.hidden) {
        wasHiddenRef.current = true;
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
      } else if (wasHiddenRef.current) {
        wasHiddenRef.current = false;
        eventSource = createEventSource();
        attachEventListeners(eventSource);
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      eventSourceRef.current?.close();
    };
  }, [queryClient]);
}
