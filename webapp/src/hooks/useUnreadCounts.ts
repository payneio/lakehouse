import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/api/client';

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
    queryFn: () =>
      fetchApi<Record<string, number>>('/api/v1/sessions/unread-counts'),
    staleTime: Infinity, // Only refetch when explicitly invalidated (via SSE)
    retry: 3,
  });
}
