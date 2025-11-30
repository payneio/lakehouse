import { useState, useEffect, useCallback } from 'react';
import { useEventStream } from './useEventStream';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  status: 'streaming' | 'complete' | 'error';
}

interface UseMessageStreamOptions {
  sessionId: string;
  onComplete?: () => void;
}

export function useMessageStream({ sessionId, onComplete }: UseMessageStreamOptions) {
  const eventStream = useEventStream({ sessionId });
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<Message | null>(null);

  useEffect(() => {
    return eventStream.on('user_message', (data) => {
      const msg: Message = {
        id: `msg-${Date.now()}-user`,
        role: 'user',
        content: data.content,
        timestamp: data.timestamp || new Date().toISOString(),
        status: 'complete',
      };
      setMessages((prev) => [...prev, msg]);
    });
  }, [eventStream]);

  useEffect(() => {
    return eventStream.on('content', (data) => {
      setStreamingMessage((prev) => {
        if (!prev) {
          return {
            id: `msg-${Date.now()}-assistant`,
            role: 'assistant',
            content: data.content || '',
            timestamp: new Date().toISOString(),
            status: 'streaming',
          };
        } else {
          return {
            ...prev,
            content: prev.content + (data.content || ''),
          };
        }
      });
    });
  }, [eventStream]);

  useEffect(() => {
    return eventStream.on('done', () => {
      if (streamingMessage) {
        setMessages((prev) => [
          ...prev,
          { ...streamingMessage, status: 'complete' },
        ]);
        setStreamingMessage(null);
      }
      onComplete?.();
    });
  }, [eventStream, streamingMessage, onComplete]);

  useEffect(() => {
    return eventStream.on('error', (data) => {
      if (streamingMessage) {
        setMessages((prev) => [
          ...prev,
          { ...streamingMessage, status: 'error' },
        ]);
        setStreamingMessage(null);
      }
      console.error('Stream error:', data.error);
    });
  }, [eventStream, streamingMessage]);

  const sendMessage = useCallback(
    async (content: string) => {
      try {
        const response = await fetch(`/api/v1/sessions/${sessionId}/send-message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
        });

        if (!response.ok) {
          throw new Error('Failed to send message');
        }
      } catch (error) {
        console.error('Error sending message:', error);
        throw error;
      }
    },
    [sessionId]
  );

  return {
    messages: streamingMessage ? [...messages, streamingMessage] : messages,
    streamingMessage,
    sendMessage,
    status: eventStream.state.status,
  };
}
