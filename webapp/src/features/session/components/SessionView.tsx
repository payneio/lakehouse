import { BASE_URL } from "@/api/client";
import { listProfiles } from "@/api/profiles";
import { changeProfile } from "@/api/sessions";
import { SessionNameEdit } from "@/features/directories/components/SessionNameEdit";
import { useEventStream } from "@/hooks/useEventStream";
import type { SessionMessage } from "@/types/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, Play, RefreshCw } from "lucide-react";
import React from "react";
import { useNavigate, useParams } from "react-router";
import { useExecutionState } from "../hooks/useExecutionState";
import { useSession } from "../hooks/useSession";
import { ApprovalDialog } from "./ApprovalDialog";
import { ExecutionPanel } from "./ExecutionPanel";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";
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

  // SSE messages ONLY (don't duplicate transcript)
  const [sseMessages, setSseMessages] = React.useState<SessionMessage[]>([]);

  // Initialize execution state
  const executionState = useExecutionState({ sessionId: sessionId || "" });

  // Log execution state for debugging
  React.useEffect(() => {
    const state = executionState.getState();
    console.log("[SessionView] Execution state:", {
      turnsCount: state.turns.length,
      currentTurn: state.currentTurn,
      metrics: state.metrics,
    });
  }, [executionState]);

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
  // Note: Only depend on sessionId and stable 'on' function (from useCallback),
  // not the full eventStream object which changes on every state update
  React.useEffect(() => {
    if (!sessionId) return;

    const unsubscribers = [
      // User message saved
      eventStream.on("user_message_saved", (data: unknown) => {
        console.log("[SessionView] user_message_saved event:", data);
        const msgData = data as MessageEventData;
        setSseMessages((prev) => {
          const updated = [
            ...prev,
            {
              role: "user" as const,
              content: msgData.content,
              timestamp: msgData.timestamp,
            },
          ];
          return updated;
        });
        // Start new execution turn
        console.log("[SessionView] Calling executionState.startTurn");
        executionState.startTurn(msgData.content);
      }),

      // Assistant message start
      eventStream.on("assistant_message_start", () => {
        setStreamingContent("");
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
        executionState.completeTurn();
      }),

      // Tool call events
      eventStream.on("hook:tool:pre", (data: unknown) => {
        console.log("[SessionView] hook:tool:pre event:", data);
        const eventData = data as {
          hook_data?: {
            tool_name: string;
            tool_input?: Record<string, unknown>;
            parallel_group_id?: string;
          };
        };
        const toolData = eventData.hook_data;
        if (toolData) {
          console.log("[SessionView] Extracted tool data:", toolData);
          console.log("[SessionView] Calling executionState.addTool");
          executionState.addTool(
            toolData.tool_name,
            toolData.tool_input,
            toolData.parallel_group_id
          );
        } else {
          console.warn("[SessionView] No hook_data in tool:pre event");
        }
      }),

      eventStream.on("hook:tool:post", (data: unknown) => {
        console.log("[SessionView] ======= RAW hook:tool:post event =======");
        console.log("[SessionView] Full event data:", JSON.stringify(data, null, 2));

        const eventData = data as {
          hook_data?: {
            tool_name: string;
            parallel_group_id?: string;
            result?: unknown;  // Loop module sends "result", not "tool_result"
            is_error?: boolean;
          };
        };

        const toolData = eventData.hook_data;
        if (toolData) {
          console.log("[SessionView] Extracted tool data:", toolData);
          console.log("[SessionView] Result being passed to updateTool:", toolData.result);
          console.log("[SessionView] Calling updateTool with name:", toolData.tool_name, "parallelGroupId:", toolData.parallel_group_id);
          executionState.updateTool(
            toolData.tool_name,
            toolData.parallel_group_id,
            {
              status: toolData.is_error ? "error" : "completed",
              endTime: Date.now(),
              result: toolData.result,  // Use "result" field from loop module
              error: toolData.is_error ? String(toolData.result) : undefined,
            }
          );
        } else {
          console.warn("[SessionView] No hook_data in tool:post event");
        }
      }),

      // Thinking events
      eventStream.on("hook:thinking:delta", (data: unknown) => {
        const eventData = data as { hook_data?: { delta: string } };
        const thinkingData = eventData.hook_data;
        if (thinkingData?.delta) {
          executionState.addThinking(thinkingData.delta);
        }
      }),
    ];

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, eventStream.on, executionState]); // Include executionState handlers

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
      <div className="border-b p-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <SessionNameEdit
              sessionId={sessionId || ""}
              currentName={session.name}
              createdAt={session.createdAt}
            />
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span>Status: {session.status}</span>
              {/* Profile dropdown */}
              <div className="flex items-center gap-2">
                <span>Profile:</span>
                <select
                  value={session.profileName}
                  onChange={(e) => handleProfileChange(e.target.value)}
                  disabled={
                    !canChangeProfile || changeProfileMutation.isPending
                  }
                  className="bg-background border border-border rounded px-2 py-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:border-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  title={
                    !canChangeProfile
                      ? "Profile can only be changed for active sessions"
                      : "Change profile"
                  }
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

                {/* Amplified directory */}
                {session.amplifiedDir && (
                  <span
                    aria-label={`Amplified directory: ${session.amplifiedDir}`}
                    title={session.amplifiedDir}
                    className="hidden sm:inline"
                  >
                    dir: /{session.amplifiedDir}
                  </span>
                )}
              </div>
            </div>
          </div>
          {/* Execution Panel Toggle */}
          <button
            onClick={() => {
              console.log(
                "[SessionView] Toggle execution panel. Currently:",
                executionPanelOpen
              );
              setExecutionPanelOpen(!executionPanelOpen);
            }}
            className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors"
            title="Toggle execution trace"
          >
            <Activity className="h-4 w-4" />
            <span className="hidden sm:inline">Trace</span>
          </button>
          {needsStart && (
            <button
              onClick={() => startSession.mutate(undefined)}
              disabled={startSession.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {startSession.isPending ? "Starting..." : "Start Session"}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <MessageList
        messages={allMessages}
        streamingContent={streamingContent}
        currentActivity={(() => {
          const activity = executionState.getCurrentActivity();
          console.log("[SessionView] Current activity:", activity);
          return activity;
        })()}
        currentTurnThinking={
          executionState.getState().currentTurn?.thinking || []
        }
      />

      {/* Tool call display */}
      <div className="px-4">
        <ToolCallDisplay
          sessionId={sessionId || ""}
          eventStream={eventStream}
        />
      </div>

      {/* Input */}
      <MessageInput onSend={handleSend} disabled={needsStart || isSending} />

      {/* Approval dialog */}
      <ApprovalDialog sessionId={sessionId || ""} />

      {/* Execution Panel */}
      <ExecutionPanel
        executionState={executionState.getState()}
        isOpen={executionPanelOpen}
        onClose={() => setExecutionPanelOpen(false)}
        onOpen={() => setExecutionPanelOpen(true)}
      />
    </div>
  );
}
