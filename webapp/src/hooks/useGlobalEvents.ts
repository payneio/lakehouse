import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BASE_URL } from '@/api/client';

/**
 * Global event stream hook that subscribes to system-wide events.
 * This should be used at the app root to handle global state updates.
 *
 * Handles:
 * - session:created - Invalidates sessions list and unread counts
 * - session:updated - Updates cached session data and unread counts
 */
export function useGlobalEvents() {
  const queryClient = useQueryClient();

  useEffect(() => {
    console.log('[useGlobalEvents] Connecting to global event stream');
    const eventSource = new EventSource(`${BASE_URL}/api/v1/events`, { withCredentials: true });

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

    return () => {
      console.log('[useGlobalEvents] Closing global event stream');
      eventSource.close();
    };
  }, [queryClient]);
}
