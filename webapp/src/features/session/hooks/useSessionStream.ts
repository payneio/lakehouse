import { useEffect, useState } from 'react';

export interface StreamEvent {
  type: string;
  data: unknown;
}

export function useSessionStream(sessionId: string, enabled: boolean) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId) {
      return;
    }

    // Note: This is for future SSE streaming implementation
    // Currently, session messages use polling via useSession
    // To implement: create SSE endpoint on backend and connect here

    return () => {
      // Cleanup when component unmounts
      setIsConnected(false);
    };
  }, [sessionId, enabled]);

  const clearEvents = () => setEvents([]);

  return {
    events,
    isConnected,
    error,
    clearEvents,
  };
}
