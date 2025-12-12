import { useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BASE_URL } from '@/api/client';

/**
 * Hook to automatically mark a session as read after viewing it for 2 seconds.
 * Also provides a manual mark-read mutation if needed.
 *
 * @param sessionId - The session to mark as read (undefined disables auto-marking)
 */
export function useMarkSessionRead(sessionId: string | undefined) {
  const queryClient = useQueryClient();

  const markRead = useMutation({
    mutationFn: async (sid: string) => {
      console.log('[useMarkSessionRead] Marking session as read:', sid);
      const response = await fetch(
        `${BASE_URL}/api/v1/sessions/${sid}/mark-read`,
        { method: 'POST' }
      );
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to mark session as read: ${error}`);
      }
      return response.json();
    },
    onSuccess: (_, sid) => {
      console.log('[useMarkSessionRead] Session marked as read:', sid);
      // Query invalidation happens via SSE session:updated event
      // But also invalidate locally for immediate feedback
      queryClient.invalidateQueries({ queryKey: ['unread-counts'] });
    },
    onError: (error) => {
      console.error('[useMarkSessionRead] Failed to mark session as read:', error);
    },
  });

  useEffect(() => {
    if (!sessionId) return;

    console.log('[useMarkSessionRead] Starting timer for session:', sessionId);

    // Mark as read after 2 seconds of viewing (debounced)
    const timer = setTimeout(() => {
      console.log('[useMarkSessionRead] Timer expired, marking session as read');
      markRead.mutate(sessionId);
    }, 2000);

    return () => {
      console.log('[useMarkSessionRead] Clearing timer for session:', sessionId);
      clearTimeout(timer);
    };
  }, [sessionId, markRead]);

  // Return mutation in case manual marking is needed
  return markRead;
}
