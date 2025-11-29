import React from 'react';
import { useParams, useNavigate } from 'react-router';
import { ArrowLeft, Play } from 'lucide-react';
import { useSession } from '../hooks/useSession';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';

export function SessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  if (!sessionId) {
    return <div>No session ID provided</div>;
  }

  const { session, transcript, isLoading, startSession } = useSession(sessionId);
  const [isSending, setIsSending] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState<string>('');

  const handleSend = async (message: string) => {
    setIsSending(true);
    setStreamingContent(''); // Clear previous streaming content
    try {
      await api.executeWithSSE(sessionId, message, {
        onMessage: (msg) => {
          console.log('SSE message received:', msg);
          console.log('SSE message.data:', msg.data);
          console.log('SSE message.data type:', typeof msg.data);

          // Accumulate streaming content for real-time display
          const data = msg.data as { type: string; content: string };
          console.log('Parsed data.type:', data.type);
          console.log('Parsed data.content:', data.content);

          if (data.type === 'content' && data.content) {
            console.log('Updating streamingContent with:', data.content);
            setStreamingContent((prev) => {
              const updated = prev + data.content;
              console.log('New streamingContent:', updated);
              return updated;
            });
          } else {
            console.log('Skipping message - type:', data.type, 'has content:', !!data.content);
          }
        },
        onComplete: () => {
          // Refresh transcript after execution completes
          queryClient.invalidateQueries({ queryKey: ['transcript', sessionId] });
          setStreamingContent(''); // Clear streaming content
          setIsSending(false);
        },
        onError: (error) => {
          console.error('SSE error:', error);
          setStreamingContent(''); // Clear on error
          setIsSending(false);
        },
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      setStreamingContent(''); // Clear on error
      setIsSending(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading session...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Session not found</div>
      </div>
    );
  }

  const needsStart = session.status === 'created';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b p-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-xl font-bold">Session: {sessionId}</h1>
            <p className="text-sm text-muted-foreground">
              Profile: {session.profileName} • Status: {session.status}
            </p>
          </div>
          {needsStart && (
            <button
              onClick={() => startSession.mutate(undefined)}
              disabled={startSession.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {startSession.isPending ? 'Starting...' : 'Start Session'}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <MessageList
        messages={transcript}
        streamingContent={streamingContent}
      />

      {/* Input */}
      <MessageInput
        onSend={handleSend}
        disabled={needsStart || isSending}
      />
    </div>
  );
}
