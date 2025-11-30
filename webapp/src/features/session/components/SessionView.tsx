import React from 'react';
import { useParams, useNavigate } from 'react-router';
import { ArrowLeft, Play, RefreshCw } from 'lucide-react';
import { useSession } from '../hooks/useSession';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ToolCallDisplay } from './ToolCallDisplay';
import { ApprovalDialog } from './ApprovalDialog';
import { useEventStream } from '@/hooks/useEventStream';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listProfiles } from '@/api/profiles';
import { changeProfile } from '@/api/sessions';
import { BASE_URL } from '@/api/client';
import type { SessionMessage } from '@/types/api';

interface MessageEventData {
  role?: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ContentEventData {
  type: string;
  content: string;
}

export function SessionView() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Hooks must be called unconditionally
  const { session, transcript, isLoading, startSession } = useSession(sessionId || '');
  const [isSending, setIsSending] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState<string>('');

  // Local message state (initialized from transcript, updated via SSE)
  const [localMessages, setLocalMessages] = React.useState<SessionMessage[]>([]);

  // Fetch available profiles
  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: listProfiles,
  });

  // Build sorted list of full profile names (collection/profile)
  const profileOptions = React.useMemo(() => {
    if (!profiles) return [];

    return profiles
      .map((profile) => {
        // Construct full name: collection/profile
        const fullName = profile.collectionId
          ? `${profile.collectionId}/${profile.name}`
          : profile.name;
        return fullName;
      })
      .sort(); // Sort alphabetically
  }, [profiles]);

  // Profile change mutation
  const changeProfileMutation = useMutation({
    mutationFn: ({ sessionId, profileName }: { sessionId: string; profileName: string }) =>
      changeProfile(sessionId, profileName),
    onSuccess: () => {
      // Refresh session data
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
    },
    onError: (error: Error) => {
      console.error('Failed to change profile:', error);
      alert(`Failed to change profile: ${error.message}`);
    },
  });

  // SSE connection for all updates (call unconditionally)
  const eventStream = useEventStream({
    sessionId: sessionId || '',
    onError: (error) => {
      console.error('SSE connection error:', error);
    },
  });

  // Initialize messages from transcript on first load
  // Track if we've already initialized to prevent infinite loops
  const transcriptInitialized = React.useRef(false);

  React.useEffect(() => {
    if (transcript && !transcriptInitialized.current) {
      setLocalMessages(transcript);
      transcriptInitialized.current = true;
    }
  }, [transcript]);

  // Reset when sessionId changes
  React.useEffect(() => {
    transcriptInitialized.current = false;
    setLocalMessages([]);
  }, [sessionId]);

  // Wire up SSE event handlers
  // Note: Only depend on sessionId and stable 'on' function (from useCallback),
  // not the full eventStream object which changes on every state update
  React.useEffect(() => {
    if (!sessionId) return;

    console.log('[SessionView] Setting up SSE handlers for:', sessionId);

    const unsubscribers = [
      // User message saved
      eventStream.on('user_message_saved', (data: unknown) => {
        console.log('[SSE Event] user_message_saved:', data);
        const msgData = data as MessageEventData;
        setLocalMessages((prev) => {
          const updated = [...prev, {
            role: 'user' as const,
            content: msgData.content,
            timestamp: msgData.timestamp,
          }];
          console.log('[State] localMessages updated, count:', updated.length);
          return updated;
        });
      }),

      // Assistant message start
      eventStream.on('assistant_message_start', () => {
        setStreamingContent('');
      }),

      // Content streaming
      eventStream.on('content', (data: unknown) => {
        const contentData = data as ContentEventData;
        console.log('[SSE Event] content, length:', contentData.content?.length);
        if (contentData.type === 'content' && contentData.content) {
          setStreamingContent((prev) => prev + contentData.content);
        }
      }),

      // Assistant message complete
      eventStream.on('assistant_message_complete', (data: unknown) => {
        console.log('[SSE Event] assistant_message_complete:', data);
        const msgData = data as MessageEventData;
        setLocalMessages((prev) => {
          const updated = [...prev, {
            role: 'assistant' as const,
            content: msgData.content,
            timestamp: msgData.timestamp,
          }];
          console.log('[State] localMessages after assistant complete, count:', updated.length);
          return updated;
        });
        setStreamingContent('');
        setIsSending(false);
      }),
    ];

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, eventStream.on]); // Only depend on sessionId and stable 'on' - full eventStream would cause loops

  const handleSend = async (message: string) => {
    setIsSending(true);
    setStreamingContent('');

    try {
      // POST to send-message (triggers execution, returns immediately)
      // All events come via persistent /stream connection
      const response = await fetch(`${BASE_URL}/api/v1/sessions/${sessionId}/send-message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: message }),
      });

      if (!response.ok) {
        throw new Error(`Send message failed: ${response.status}`);
      }

      // Execution triggered in background
      // All events (user_message_saved, content, assistant_message_complete) come via /stream
      // assistant_message_complete event will set isSending=false
    } catch (error) {
      console.error('Failed to send message:', error);
      setStreamingContent('');
      setIsSending(false);
    }
  };

  // Handle profile change
  const handleProfileChange = (newProfileName: string) => {
    if (!sessionId) return;

    // Only allow profile change if session is active
    if (session?.status !== 'active') {
      alert('Can only change profile for active sessions');
      return;
    }

    if (confirm(`Switch to profile "${newProfileName}"? This will reload the session configuration.`)) {
      changeProfileMutation.mutate({ sessionId, profileName: newProfileName });
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
  const canChangeProfile = session.status === 'active';

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
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span>Status: {session.status}</span>
              {/* Profile dropdown */}
              <div className="flex items-center gap-2">
                <span>Profile:</span>
                <select
                  value={session.profileName}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  disabled={!canChangeProfile || changeProfileMutation.isPending}
                  className="bg-background border border-border rounded px-2 py-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:border-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  title={!canChangeProfile ? 'Profile can only be changed for active sessions' : 'Change profile'}
                >
                  {profileOptions.map((fullName) => (
                    <option key={fullName} value={fullName}>
                      {fullName}
                    </option>
                  ))}
                </select>
                {changeProfileMutation.isPending && (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                )}
              </div>
            </div>
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
        messages={localMessages}
        streamingContent={streamingContent}
      />

      {/* Tool call display */}
      <div className="px-4">
        <ToolCallDisplay sessionId={sessionId || ''} eventStream={eventStream} />
      </div>

      {/* Input */}
      <MessageInput
        onSend={handleSend}
        disabled={needsStart || isSending}
      />

      {/* Approval dialog */}
      <ApprovalDialog sessionId={sessionId || ''} />
    </div>
  );
}
