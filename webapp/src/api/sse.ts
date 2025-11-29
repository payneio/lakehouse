import { BASE_URL } from './client';

export interface SSEMessage {
  event: string;
  data: unknown;
}

export interface SSEHandlers {
  onMessage: (message: SSEMessage) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

/**
 * Execute a message with SSE streaming support using POST
 */
export async function executeWithSSE(
  sessionId: string,
  content: string,
  handlers: SSEHandlers
): Promise<void> {
  const url = `${BASE_URL}/api/v1/sessions/${sessionId}/execute`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'message';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          handlers.onComplete?.();
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events (delimited by double newline)
        while (buffer.includes('\n\n')) {
          const eventEndIndex = buffer.indexOf('\n\n');
          const eventBlock = buffer.substring(0, eventEndIndex);
          buffer = buffer.substring(eventEndIndex + 2);

          // Parse event block
          let eventType = 'message';
          let eventData: string | null = null;

          const lines = eventBlock.split('\n');
          for (const line of lines) {
            const trimmedLine = line.replace('\r', '').trim();
            if (!trimmedLine) continue;

            if (trimmedLine.startsWith('event:')) {
              eventType = trimmedLine.substring(6).trim();
            } else if (trimmedLine.startsWith('data:')) {
              eventData = trimmedLine.substring(5).trim();
            }
          }

          // Process the event if we have data
          if (eventData) {
            try {
              const parsed = JSON.parse(eventData);
              handlers.onMessage({
                event: eventType,
                data: parsed,
              });
            } catch (e) {
              console.warn('Failed to parse SSE data as JSON:', eventData, e);
              handlers.onMessage({
                event: eventType,
                data: { content: eventData },
              });
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } catch (error) {
    handlers.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}
