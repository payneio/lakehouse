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
    onSuccess: () => {
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

    // Mark as read after 2 seconds of viewing (debounced)
    const timer = setTimeout(() => {
      markRead.mutate(sessionId);
    }, 2000);

    return () => {
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]); // markRead omitted intentionally - stable mutation object

  // Return mutation in case manual marking is needed
  return markRead;
}
