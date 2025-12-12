import { useQuery } from '@tanstack/react-query';
import { BASE_URL } from '@/api/client';

/**
 * Hook to fetch unread session counts per project.
 * Returns a map of project path -> unread count.
 *
 * Uses infinite staleTime to rely on explicit invalidation via SSE events.
 * This ensures counts are always up-to-date without unnecessary polling.
 */
export function useUnreadCounts() {
  return useQuery<Record<string, number>>({
    queryKey: ['unread-counts'],
    queryFn: async () => {
      console.log('[useUnreadCounts] Fetching unread counts');
      const response = await fetch(`${BASE_URL}/api/v1/sessions/unread-counts`);
      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Failed to fetch unread counts: ${error}`);
      }
      const counts = await response.json();
      console.log('[useUnreadCounts] Fetched counts:', counts);
      return counts;
    },
    staleTime: Infinity, // Only refetch when explicitly invalidated (via SSE)
    retry: 3,
  });
}
