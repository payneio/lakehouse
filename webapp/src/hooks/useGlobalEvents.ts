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
      console.log('[useGlobalEvents] Connecting to global event stream');
      const eventSource = new EventSource(`${BASE_URL}/api/v1/events`);
      eventSourceRef.current = eventSource;
      return eventSource;
    }

    let eventSource = createEventSource();

    // Handle session:created events
    eventSource.addEventListener('session:created', (e) => {
      const event = JSON.parse(e.data);
      console.log('[useGlobalEvents] session:created:', event);

      // Invalidate sessions list for this project
      queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });

      // Invalidate unread counts
      queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
    });

    // Handle session:updated events (read state changes)
    eventSource.addEventListener('session:updated', (e) => {
      const event = JSON.parse(e.data);
      console.log('[useGlobalEvents] session:updated:', event);

      // If is_unread changed, update related queries
      if (event.fields_changed?.includes('is_unread')) {
        // Invalidate unread counts - will refetch with correct values
        queryClient.invalidateQueries({ queryKey: ['unread-counts'] });

        // Invalidate cached session data to force refetch
        queryClient.invalidateQueries({ queryKey: ['session', event.session_id] });

        // Invalidate sessions list for this project
        queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
      }
    });

    // Handle connection events
    eventSource.addEventListener('connected', () => {
      console.log('[useGlobalEvents] Connected to global events');
    });

    eventSource.addEventListener('keepalive', () => {
      // Silent keepalive - no logging needed
    });

    eventSource.onerror = (error) => {
      console.error('[useGlobalEvents] Event stream error:', error);
    };

    // Handle visibility changes for mobile app backgrounding
    // When app is hidden, close SSE to save resources
    // When app becomes visible again, reconnect without full page reload
    function handleVisibilityChange() {
      if (document.hidden) {
        console.log('[useGlobalEvents] App hidden, closing SSE connection');
        wasHiddenRef.current = true;
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
      } else if (wasHiddenRef.current) {
        console.log('[useGlobalEvents] App visible again, reconnecting SSE');
        wasHiddenRef.current = false;
        eventSource = createEventSource();
        // Re-attach event listeners to new EventSource
        attachEventListeners(eventSource);
      }
    }

    function attachEventListeners(es: EventSource) {
      es.addEventListener('session:created', (e) => {
        const event = JSON.parse(e.data);
        console.log('[useGlobalEvents] session:created:', event);
        queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
        queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
      });

      es.addEventListener('session:updated', (e) => {
        const event = JSON.parse(e.data);
        console.log('[useGlobalEvents] session:updated:', event);
        if (event.fields_changed?.includes('is_unread')) {
          queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
          queryClient.invalidateQueries({ queryKey: ['session', event.session_id] });
          queryClient.invalidateQueries({ queryKey: ['sessions', event.project_id] });
        }
      });

      es.addEventListener('connected', () => {
        console.log('[useGlobalEvents] Connected to global events');
      });

      es.addEventListener('keepalive', () => {
        // Silent keepalive
      });

      es.onerror = (error) => {
        console.error('[useGlobalEvents] Event stream error:', error);
      };
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      console.log('[useGlobalEvents] Closing global event stream');
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      eventSourceRef.current?.close();
    };
  }, [queryClient]);
}
