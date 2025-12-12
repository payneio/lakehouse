import * as api from "@/api";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { useNavigate } from "react-router";
import { useSessions } from "../hooks/useDirectories";

interface SessionsListProps {
  directoryPath: string;
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
    },
  });

  const handleCreateSession = async () => {
    try {
      // Create session (already started by backend)
      const newSession = await createSession.mutateAsync({
        amplified_dir: directoryPath,
      });

      // Navigate to session
      navigate(`/directories/sessions/${newSession.sessionId}`);
    } catch (error) {
      console.error("Failed to create session:", error);
      // Cache invalidation in onSuccess will refresh the list
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading sessions...</div>;
  }

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

      {sessions.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No sessions found. Create one to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => (
            <div
              key={session.sessionId}
              className="border rounded-lg p-4 hover:bg-accent transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <button
                  onClick={() =>
                    navigate(`/directories/sessions/${session.sessionId}`)
                  }
                  className="flex-1 text-left"
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    <span className="font-medium">
                      {session.name ||
                        `Session from ${new Date(
                          session.createdAt
                        ).toLocaleDateString()}`}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Created: {new Date(session.createdAt).toLocaleString()}
                  </div>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("Delete this session?")) {
                      deleteSession.mutate(session.sessionId);
                    }
                  }}
                  className="text-destructive hover:text-destructive/80 p-2"
                  disabled={deleteSession.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
