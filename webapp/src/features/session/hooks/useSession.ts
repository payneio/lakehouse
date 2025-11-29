import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';

export function useSession(sessionId: string) {
  const queryClient = useQueryClient();

  const session = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.getSession(sessionId),
  });

  const transcript = useQuery({
    queryKey: ['transcript', sessionId],
    queryFn: () => api.getTranscript(sessionId),
    // No polling needed - SSE provides real-time updates, invalidateQueries handles refresh
  });

  const startSession = useMutation({
    mutationFn: () => api.startSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
  });

  return {
    session: session.data,
    transcript: transcript.data ?? [],
    isLoading: session.isLoading || transcript.isLoading,
    error: session.error || transcript.error,
    startSession,
  };
}
