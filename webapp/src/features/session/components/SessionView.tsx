import { BASE_URL } from "@/api/client";
import { listProfiles } from "@/api/profiles";
import { cancelExecution, changeProfile, deleteLastMessage } from "@/api/sessions";
import { SessionNameEdit } from "@/features/directories/components/SessionNameEdit";
import { useEventStream } from "@/hooks/useEventStream";
import { useMarkSessionRead } from "@/hooks/useMarkSessionRead";
import { useScrollDirection } from "@/hooks/useScrollDirection";
import type { SessionMessage } from "@/types/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, FileText, Play, RefreshCw } from "lucide-react";
import React from "react";
import { useNavigate, useParams } from "react-router";
import { useExecutionState } from "../hooks/useExecutionState";
import { useSession } from "../hooks/useSession";
import { ApprovalDialog } from "./ApprovalDialog";
import { ExecutionPanel } from "./ExecutionPanel";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";
import { SessionLogDialog } from "./SessionLogDialog";
import { ToolCallDisplay } from "./ToolCallDisplay";

interface MessageEventData {
  role?: "user" | "assistant";
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
  const { session, transcript, isLoading, startSession } = useSession(
    sessionId || ""
  );
  const [isSending, setIsSending] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState<string>("");
  const [executionPanelOpen, setExecutionPanelOpen] = React.useState(false);
  const [logDialogOpen, setLogDialogOpen] = React.useState(false);

  // Scroll container for header visibility (use state so effect re-runs when set)
  const [scrollContainer, setScrollContainer] = React.useState<HTMLDivElement | null>(null);

  // Track scroll direction for mobile header visibility
  const scrollDirection = useScrollDirection(10, scrollContainer);

  // Force hide header on message received, resume scroll behavior on scroll
  const [forceHideHeader, setForceHideHeader] = React.useState(false);

  // Update visibility logic to include force-hide check
  const isHeaderVisible = !forceHideHeader && scrollDirection === 'up';

  // Clear force-hide when user scrolls (resume normal behavior)
  React.useEffect(() => {
    if (forceHideHeader) {
      setForceHideHeader(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollDirection]); // Only run when scroll direction changes, not when forceHideHeader changes

  // SSE messages ONLY (don't duplicate transcript)
  const [sseMessages, setSseMessages] = React.useState<SessionMessage[]>([]);

  // Initialize execution state
  const executionState = useExecutionState({ sessionId: sessionId || "" });

  // Use ref to avoid re-subscribing SSE handlers when executionState changes
  const executionStateRef = React.useRef(executionState);
  React.useEffect(() => {
    executionStateRef.current = executionState;
  }, [executionState]);

  // Auto-mark session as read after viewing for 2 seconds
  useMarkSessionRead(sessionId);

  // Fetch available profiles
  const { data: profiles } = useQuery({
    queryKey: ["profiles"],
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
    mutationFn: ({
      sessionId,
      profileName,
    }: {
      sessionId: string;
      profileName: string;
    }) => changeProfile(sessionId, profileName),
    onSuccess: () => {
      // Refresh session data
      queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    },
    onError: (error: Error) => {
      console.error("Failed to change profile:", error);
      alert(`Failed to change profile: ${error.message}`);
    },
  });

  // SSE connection for all updates (call unconditionally)
  const eventStream = useEventStream({
    sessionId: sessionId || "",
    onError: (error) => {
      console.error("SSE connection error:", error);
    },
  });

  // Clear SSE messages when navigating to different session
  React.useEffect(() => {
    setSseMessages([]);
  }, [sessionId]);

  // Combine transcript (historical) + SSE messages (new)
  const allMessages = React.useMemo(() => {
    const combined = [...(transcript || []), ...sseMessages];
    return combined;
  }, [transcript, sseMessages]);

  // Wire up SSE event handlers
  // Note: Use executionStateRef to avoid re-subscribing when executionState changes
  React.useEffect(() => {
    if (!sessionId) return;

    const unsubscribers = [
      // User message saved
      eventStream.on("user_message_saved", (data: unknown) => {
        const msgData = data as MessageEventData;
        setSseMessages((prev) => [
          ...prev,
          {
            role: "user" as const,
            content: msgData.content,
            timestamp: msgData.timestamp,
          },
        ]);
        executionStateRef.current.startTurn(msgData.content);
      }),

      // Assistant message start
      eventStream.on("assistant_message_start", () => {
        setStreamingContent("");
        setForceHideHeader(true);
      }),

      // Content streaming
      eventStream.on("content", (data: unknown) => {
        const contentData = data as ContentEventData;
        if (contentData.type === "content" && contentData.content) {
          setStreamingContent((prev) => prev + contentData.content);
        }
      }),

      // Assistant message complete
      eventStream.on("assistant_message_complete", (data: unknown) => {
        const msgData = data as MessageEventData;
        setSseMessages((prev) => {
          const updated = [
            ...prev,
            {
              role: "assistant" as const,
              content: msgData.content,
              timestamp: msgData.timestamp,
            },
          ];
          return updated;
        });
        setStreamingContent("");
        setIsSending(false);
        // Complete execution turn
        executionStateRef.current.completeTurn();
      }),

      // Tool call events
      eventStream.on("hook:tool:pre", (data: unknown) => {
        const eventData = data as {
          hook_data?: {
            tool_name: string;
            tool_input?: Record<string, unknown>;
            parallel_group_id?: string;
          };
        };
        const toolData = eventData.hook_data;
        if (toolData) {
          executionStateRef.current.addTool(
            toolData.tool_name,
            toolData.tool_input,
            toolData.parallel_group_id
          );
        }
      }),

      eventStream.on("hook:tool:post", (data: unknown) => {
        const eventData = data as {
          hook_data?: {
            tool_name: string;
            parallel_group_id?: string;
            result?: unknown;
            is_error?: boolean;
          };
        };

        const toolData = eventData.hook_data;
        if (toolData) {
          executionStateRef.current.updateTool(
            toolData.tool_name,
            toolData.parallel_group_id,
            {
              status: toolData.is_error ? "error" : "completed",
              endTime: Date.now(),
              result: toolData.result,
              error: toolData.is_error ? String(toolData.result) : undefined,
            }
          );
        }
      }),

      // Thinking events
      eventStream.on("hook:thinking:delta", (data: unknown) => {
        const eventData = data as { hook_data?: { delta: string } };
        const thinkingData = eventData.hook_data;
        if (thinkingData?.delta) {
          executionStateRef.current.addThinking(thinkingData.delta);
        }
      }),

      // Execution cancelled
      eventStream.on("execution_cancelled", () => {
        setStreamingContent("");
        setIsSending(false);
        executionStateRef.current.completeTurn();
      }),

      // Execution error
      eventStream.on("execution_error", () => {
        setStreamingContent("");
        setIsSending(false);
        executionStateRef.current.completeTurn();
      }),

      // Message deleted (cross-client sync)
      eventStream.on("message_deleted", () => {
        // Another client (or this one) deleted a message, refetch transcript
        queryClient.invalidateQueries({ queryKey: ["transcript", sessionId] });
        setSseMessages([]); // Clear SSE messages, they'll be in transcript now
      }),
    ];

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [sessionId, eventStream.on]); // Removed executionState - use ref instead

  const handleSend = async (message: string) => {
    setIsSending(true);
    setStreamingContent("");

    try {
      // POST to send-message (triggers execution, returns immediately)
      // All events come via persistent /stream connection
      const response = await fetch(
        `${BASE_URL}/api/v1/sessions/${sessionId}/send-message`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: message }),
        }
      );

      if (!response.ok) {
        throw new Error(`Send message failed: ${response.status}`);
      }

      // Execution triggered in background
      // All events (user_message_saved, content, assistant_message_complete) come via /stream
      // assistant_message_complete event will set isSending=false
    } catch (error) {
      console.error("Failed to send message:", error);
      setStreamingContent("");
      setIsSending(false);
    }
  };

  const handleCancel = async () => {
    if (!sessionId) return;

    try {
      await cancelExecution(sessionId);
      // The execution_cancelled SSE event will handle resetting state
    } catch (error) {
      console.error("Failed to cancel execution:", error);
      // Reset state anyway in case the SSE event doesn't arrive
      setStreamingContent("");
      setIsSending(false);
    }
  };

  const handleDeleteLast = async () => {
    if (!sessionId || isSending || allMessages.length === 0) return;

    if (!confirm("Delete the last message?")) return;

    try {
      await deleteLastMessage(sessionId);
      // Optimistic update: remove from sseMessages if present, otherwise refetch
      if (sseMessages.length > 0) {
        setSseMessages((prev) => prev.slice(0, -1));
      } else {
        // Message was in transcript, need to refetch
        queryClient.invalidateQueries({ queryKey: ["transcript", sessionId] });
      }
    } catch (error) {
      console.error("Failed to delete message:", error);
      alert("Failed to delete message. Please try again.");
    }
  };

  // Handle profile change
  const handleProfileChange = (newProfileName: string) => {
    if (!sessionId) return;

    // Only allow profile change if session is active
    if (session?.status !== "active") {
      alert("Can only change profile for active sessions");
      return;
    }

    if (
      confirm(
        `Switch to profile "${newProfileName}"? This will reload the session configuration.`
      )
    ) {
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

  const needsStart = session.status === "created";
  const canChangeProfile = session.status === "active";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className={`
          border-b p-4
          transition-transform duration-300 ease-in-out
          lg:relative lg:translate-y-0
          fixed top-0 left-0 right-0 z-50 bg-background
          ${isHeaderVisible ? 'translate-y-0' : '-translate-y-full'}
        `}
      >
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-muted-foreground hover:text-foreground flex-shrink-0"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1 min-w-0">
            <SessionNameEdit
              sessionId={sessionId || ""}
              currentName={session.name}
              createdAt={session.createdAt}
            />
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {/* Profile dropdown - compact on mobile (no label) */}
              <span className="hidden sm:inline flex-shrink-0">Profile:</span>
              <select
                value={session.profileName}
                onChange={(e) => handleProfileChange(e.target.value)}
                disabled={
                  !canChangeProfile || changeProfileMutation.isPending
                }
                className="bg-background border border-border rounded px-2 py-1 text-sm max-w-[100px] sm:max-w-[150px] truncate disabled:opacity-50 disabled:cursor-not-allowed hover:border-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                title={
                  !canChangeProfile
                    ? "Profile can only be changed for active sessions"
                    : `Profile: ${session.profileName}`
                }
              >
                {profileOptions.map((fullName) => (
                  <option key={fullName} value={fullName}>
                    {fullName}
                  </option>
                ))}
              </select>
              {changeProfileMutation.isPending && (
                <RefreshCw className="h-4 w-4 animate-spin flex-shrink-0" />
              )}

              {/* Amplified directory - hidden on mobile */}
              {session.amplifiedDir && (
                <span
                  aria-label={`Amplified directory: ${session.amplifiedDir}`}
                  title={session.amplifiedDir}
                  className="hidden md:inline truncate"
                >
                  dir: /{session.amplifiedDir}
                </span>
              )}

              {/* Action buttons - on same row as profile */}
              <div className="flex items-center gap-1 ml-auto flex-shrink-0">
                <button
                  onClick={() => setExecutionPanelOpen(!executionPanelOpen)}
                  className="flex items-center gap-1 px-2 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors"
                  title="Toggle execution trace"
                >
                  <Activity className="h-4 w-4" />
                  <span className="hidden md:inline">Trace</span>
                </button>
                <button
                  onClick={() => setLogDialogOpen(true)}
                  className="flex items-center gap-1 px-2 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors"
                  title="View session events log"
                >
                  <FileText className="h-4 w-4" />
                  <span className="hidden md:inline">Log</span>
                </button>
                {needsStart && (
                  <button
                    onClick={() => startSession.mutate(undefined)}
                    disabled={startSession.isPending}
                    className="flex items-center gap-1 px-2 py-1 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 text-sm"
                  >
                    <Play className="h-4 w-4" />
                    <span className="hidden sm:inline">{startSession.isPending ? "Starting..." : "Start"}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <MessageList
        onContainerMount={setScrollContainer}
        messages={allMessages}
        streamingContent={streamingContent}
        currentActivity={executionState.getCurrentActivity()}
        currentTurnThinking={
          executionState.getState().currentTurn?.thinking || []
        }
        onDeleteLast={handleDeleteLast}
        canDeleteLast={!isSending && allMessages.length > 0}
      />

      {/* Tool call display */}
      <div className="px-4">
        <ToolCallDisplay
          sessionId={sessionId || ""}
          eventStream={eventStream}
        />
      </div>

      {/* Input */}
      <MessageInput
        onSend={handleSend}
        disabled={needsStart || isSending}
        isSending={isSending}
        onCancel={handleCancel}
      />

      {/* Approval dialog */}
      <ApprovalDialog sessionId={sessionId || ""} />

      {/* Execution Panel */}
      <ExecutionPanel
        executionState={executionState.getState()}
        isOpen={executionPanelOpen}
        onClose={() => setExecutionPanelOpen(false)}
      />

      {/* Session Log Dialog */}
      <SessionLogDialog
        sessionId={sessionId || ""}
        open={logDialogOpen}
        onClose={() => setLogDialogOpen(false)}
      />
    </div>
  );
}
