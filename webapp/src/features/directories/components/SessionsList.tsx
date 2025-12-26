import * as api from "@/api";
import type { Session } from "@/types/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useNavigate } from "react-router";
import { useSessions } from "../hooks/useDirectories";

interface SessionsListProps {
  directoryPath: string;
}

function SessionIcon({ isSubsession }: { isSubsession: boolean }) {
  if (isSubsession) {
    return <Bot className="h-4 w-4 flex-shrink-0 text-muted-foreground" />;
  }
  return <MessageSquare className="h-4 w-4 flex-shrink-0" />;
}

interface SessionCardProps {
  session: Session;
  isSubsession: boolean;
  onNavigate: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}

function SessionCard({ session, isSubsession, onNavigate, onDelete, isDeleting }: SessionCardProps) {
  return (
    <div
      className={`border rounded-lg p-4 hover:bg-accent transition-colors ${
        isSubsession ? "ml-6 border-dashed border-muted-foreground/30" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <button onClick={onNavigate} className="flex-1 text-left">
          <div className="flex items-center gap-2">
            {session.isUnread && (
              <div className="w-2 h-2 bg-primary rounded-full" title="Unread" />
            )}
            <SessionIcon isSubsession={isSubsession} />
            <span className={`${session.isUnread ? "font-bold" : "font-medium"} ${isSubsession ? "text-muted-foreground" : ""}`}>
              {session.name ||
                `Session from ${new Date(session.createdAt).toLocaleDateString()}`}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Created: {new Date(session.createdAt).toLocaleString()}
          </div>
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="text-destructive hover:text-destructive/80 p-2"
          disabled={isDeleting}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

interface SessionWithChildren extends Session {
  children: Session[];
}

function organizeSessionHierarchy(sessions: Session[]): SessionWithChildren[] {
  const sessionMap = new Map<string, Session>();
  const childrenMap = new Map<string, Session[]>();

  for (const session of sessions) {
    sessionMap.set(session.sessionId, session);
    if (session.parentSessionId) {
      const siblings = childrenMap.get(session.parentSessionId) || [];
      siblings.push(session);
      childrenMap.set(session.parentSessionId, siblings);
    }
  }

  const result: SessionWithChildren[] = [];
  const processedIds = new Set<string>();

  for (const session of sessions) {
    if (processedIds.has(session.sessionId)) continue;

    if (!session.parentSessionId) {
      const children = childrenMap.get(session.sessionId) || [];
      children.sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      );
      result.push({ ...session, children });
      processedIds.add(session.sessionId);
      children.forEach((c) => processedIds.add(c.sessionId));
    } else if (!sessionMap.has(session.parentSessionId)) {
      result.push({ ...session, children: [] });
      processedIds.add(session.sessionId);
    }
  }

  result.sort((a, b) => {
    const aLatest = Math.max(
      new Date(a.createdAt).getTime(),
      ...a.children.map((c) => new Date(c.createdAt).getTime())
    );
    const bLatest = Math.max(
      new Date(b.createdAt).getTime(),
      ...b.children.map((c) => new Date(c.createdAt).getTime())
    );
    return bLatest - aLatest;
  });

  return result;
}

export function SessionsList({ directoryPath }: SessionsListProps) {
  const { sessions, isLoading } = useSessions(directoryPath);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const createSession = useMutation({
    mutationFn: (data: { profile_name?: string; amplified_dir?: string }) =>
      api.createSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const deleteSession = useMutation({
    mutationFn: (sessionId: string) => api.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["unread-counts"] });
    },
  });

  const handleCreateSession = async () => {
    try {
      const newSession = await createSession.mutateAsync({
        amplified_dir: directoryPath,
      });
      navigate(`/directories/sessions/${newSession.sessionId}`);
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading sessions...</div>;
  }

  const hierarchicalSessions = organizeSessionHierarchy(sessions);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Chat Sessions</h2>
        <button
          onClick={handleCreateSession}
          disabled={createSession.isPending}
          className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          {createSession.isPending ? "Creating..." : "New Session"}
        </button>
      </div>

      {hierarchicalSessions.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No sessions found. Create one to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {hierarchicalSessions.map((session) => {
            const isSubsession = !!session.parentSessionId;
            return (
              <div key={session.sessionId}>
                <SessionCard
                  session={session}
                  isSubsession={isSubsession}
                  onNavigate={() => navigate(`/directories/sessions/${session.sessionId}`)}
                  onDelete={() => {
                    if (confirm("Delete this session?")) {
                      deleteSession.mutate(session.sessionId);
                    }
                  }}
                  isDeleting={deleteSession.isPending}
                />
                {session.children.length > 0 && (
                  <div className="mt-1 space-y-1">
                    {session.children.map((child) => (
                      <SessionCard
                        key={child.sessionId}
                        session={child}
                        isSubsession={true}
                        onNavigate={() => navigate(`/directories/sessions/${child.sessionId}`)}
                        onDelete={() => {
                          if (confirm("Delete this session?")) {
                            deleteSession.mutate(child.sessionId);
                          }
                        }}
                        isDeleting={deleteSession.isPending}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
