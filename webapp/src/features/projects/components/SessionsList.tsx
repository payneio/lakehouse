import * as api from "@/api";
import type { Session } from "@/types/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useSessions } from "../hooks/useProjects";

/** Extract a human-readable message from an API error (FastAPI sends {"detail": ...}). */
function errorDetail(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON — fall through
  }
  return raw;
}

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
  isSelected: boolean;
  onToggleSelect: (modifiers: { shiftKey: boolean }) => void;
}

function SessionCard({
  session,
  isSubsession,
  onNavigate,
  onDelete,
  isDeleting,
  isSelected,
  onToggleSelect,
}: SessionCardProps) {
  return (
    <div
      className={`border rounded-lg p-4 transition-colors ${
        isSelected ? "bg-accent border-primary" : "hover:bg-accent"
      } ${isSubsession ? "ml-6 border-dashed border-muted-foreground/30" : ""}`}
    >
      <div className="flex items-start justify-between gap-4">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => {}}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect({ shiftKey: e.shiftKey });
          }}
          className="mt-1 h-4 w-4 flex-shrink-0 cursor-pointer accent-primary"
          aria-label="Select session"
        />
        <button onClick={onNavigate} className="flex-1 text-left">
          <div className="flex items-center gap-2">
            {session.isUnread && (
              <div className="w-2 h-2 bg-primary rounded-full" title="Unread" />
            )}
            <SessionIcon isSubsession={isSubsession} />
            <span
              className={`${session.isUnread ? "font-bold" : "font-medium"} ${isSubsession ? "text-muted-foreground" : ""}`}
            >
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
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
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
      ...a.children.map((c) => new Date(c.createdAt).getTime()),
    );
    const bLatest = Math.max(
      new Date(b.createdAt).getTime(),
      ...b.children.map((c) => new Date(c.createdAt).getTime()),
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
    mutationFn: (data: { assistant_name?: string; project_path?: string }) =>
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

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [anchorId, setAnchorId] = useState<string | null>(null);

  const deleteSelected = useMutation({
    mutationFn: (sessionIds: string[]) =>
      Promise.all(sessionIds.map((id) => api.deleteSession(id))),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["unread-counts"] });
      setSelectedIds(new Set());
    },
  });

  const toggleSelect = (
    sessionId: string,
    { shiftKey }: { shiftKey: boolean },
  ) => {
    // Flat list of every session id in display order (parents then their children).
    const ordered = organizeSessionHierarchy(sessions).flatMap((s) => [
      s.sessionId,
      ...s.children.map((c) => c.sessionId),
    ]);

    setSelectedIds((prev) => {
      const next = new Set(prev);
      const anchorIndex = anchorId ? ordered.indexOf(anchorId) : -1;
      const targetIndex = ordered.indexOf(sessionId);

      if (shiftKey && anchorIndex !== -1 && targetIndex !== -1) {
        // Range select: add everything between the anchor and the clicked row.
        const [lo, hi] =
          anchorIndex < targetIndex
            ? [anchorIndex, targetIndex]
            : [targetIndex, anchorIndex];
        for (let i = lo; i <= hi; i++) next.add(ordered[i]);
      } else if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      return next;
    });

    // Plain/ctrl clicks move the anchor; shift extends from the existing anchor.
    if (!shiftKey) {
      setAnchorId(sessionId);
    }
  };

  const markSelectedRead = useMutation({
    mutationFn: (sessionIds: string[]) =>
      Promise.all(sessionIds.map((id) => api.markSessionRead(id))),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["unread-counts"] });
      setSelectedIds(new Set());
    },
  });

  const handleMarkSelectedRead = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    markSelectedRead.mutate(ids);
  };

  const handleDeleteSelected = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    if (confirm(`Delete ${ids.length} session${ids.length === 1 ? "" : "s"}?`)) {
      deleteSelected.mutate(ids);
    }
  };

  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreateSession = async () => {
    setCreateError(null);
    try {
      const newSession = await createSession.mutateAsync({
        project_path: directoryPath,
      });
      navigate(`/projects/sessions/${newSession.sessionId}`);
    } catch (error) {
      console.error("Failed to create session:", error);
      setCreateError(errorDetail(error));
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading sessions...</div>;
  }

  const hierarchicalSessions = organizeSessionHierarchy(sessions);
  const allSessionIds = hierarchicalSessions.flatMap((session) => [
    session.sessionId,
    ...session.children.map((c) => c.sessionId),
  ]);
  const allSelected =
    allSessionIds.length > 0 && selectedIds.size === allSessionIds.length;

  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(allSessionIds));
  };

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

      {createError && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Failed to create session: {createError}
        </div>
      )}

      {allSessionIds.length > 0 && (
        <div className="flex items-center justify-between gap-4 rounded-md border bg-muted/40 px-3 py-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleSelectAll}
              className="h-4 w-4 cursor-pointer accent-primary"
            />
            {selectedIds.size > 0
              ? `${selectedIds.size} selected`
              : "Select all"}
          </label>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSelectedIds(new Set())}
                className="px-3 py-1.5 text-sm rounded-md hover:bg-accent"
              >
                Clear
              </button>
              <button
                onClick={handleMarkSelectedRead}
                disabled={markSelectedRead.isPending}
                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border hover:bg-accent disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                {markSelectedRead.isPending ? "Marking..." : "Mark read"}
              </button>
              <button
                onClick={handleDeleteSelected}
                disabled={deleteSelected.isPending}
                className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                {deleteSelected.isPending
                  ? "Deleting..."
                  : `Delete ${selectedIds.size}`}
              </button>
            </div>
          )}
        </div>
      )}

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
                  isSelected={selectedIds.has(session.sessionId)}
                  onToggleSelect={(m) => toggleSelect(session.sessionId, m)}
                  onNavigate={() =>
                    navigate(`/projects/sessions/${session.sessionId}`)
                  }
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
                        isSelected={selectedIds.has(child.sessionId)}
                        onToggleSelect={(m) => toggleSelect(child.sessionId, m)}
                        onNavigate={() =>
                          navigate(`/projects/sessions/${child.sessionId}`)
                        }
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
