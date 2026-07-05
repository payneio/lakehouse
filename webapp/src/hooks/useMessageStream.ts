import { useState, useEffect, useCallback } from 'react';
import { useEventStream } from './useEventStream';
import { sendMessage as sendMessageApi } from '@/api/sessions';

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
      const eventData = data as { content?: string; timestamp?: string };
      const msg: Message = {
        id: `msg-${Date.now()}-user`,
        role: 'user',
        content: eventData.content || '',
        timestamp: eventData.timestamp || new Date().toISOString(),
        status: 'complete',
      };
      setMessages((prev) => [...prev, msg]);
    });
  }, [eventStream]);

  useEffect(() => {
    return eventStream.on('content', (data) => {
      const eventData = data as { content?: string };
      setStreamingMessage((prev) => {
        if (!prev) {
          return {
            id: `msg-${Date.now()}-assistant`,
            role: 'assistant',
            content: eventData.content || '',
            timestamp: new Date().toISOString(),
            status: 'streaming',
          };
        } else {
          return {
            ...prev,
            content: prev.content + (eventData.content || ''),
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
      const eventData = data as { error?: string };
      if (streamingMessage) {
        setMessages((prev) => [
          ...prev,
          { ...streamingMessage, status: 'error' },
        ]);
        setStreamingMessage(null);
      }
      console.error('Stream error:', eventData.error);
    });
  }, [eventStream, streamingMessage]);

  const sendMessage = useCallback(
    async (content: string) => {
      try {
        await sendMessageApi(sessionId, content);
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
