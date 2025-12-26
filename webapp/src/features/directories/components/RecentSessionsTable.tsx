import { FolderOpen, MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { useAllSessions } from "../hooks/useDirectories";

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function getProjectName(amplifiedDir?: string): string {
  if (!amplifiedDir) return "No project";
  const parts = amplifiedDir.split("/");
  return parts[parts.length - 1] || amplifiedDir;
}

export function RecentSessionsTable() {
  const { sessions, isLoading, error } = useAllSessions(20);

  if (isLoading) {
    return (
      <div className="text-muted-foreground text-center py-8">
        Loading recent sessions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-destructive text-center py-8">
        Failed to load sessions
      </div>
    );
  }

  // Sort by createdAt descending (most recent first)
  const sortedSessions = [...sessions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  if (sortedSessions.length === 0) {
    return (
      <div className="text-muted-foreground text-center py-8">
        No sessions yet. Select a project and start a chat.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Mobile view: card layout */}
      <div className="sm:hidden space-y-2">
        {sortedSessions.map((session) => (
          <div
            key={session.sessionId}
            className="border rounded-lg p-3 space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <Link
                to={`/directories/sessions/${session.sessionId}`}
                className="flex items-center gap-2 hover:text-primary min-w-0 flex-1"
              >
                {session.isUnread && (
                  <span className="w-2 h-2 bg-primary rounded-full flex-shrink-0" />
                )}
                <MessageSquare className="h-4 w-4 flex-shrink-0" />
                <span className={`truncate ${session.isUnread ? "font-bold" : ""}`}>
                  {session.name ||
                    `Session ${new Date(session.createdAt).toLocaleDateString()}`}
                </span>
              </Link>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(session.createdAt)}
              </span>
            </div>
            {session.amplifiedDir && (
              <Link
                to={`/directories?path=${encodeURIComponent(session.amplifiedDir)}`}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
              >
                <FolderOpen className="h-3 w-3" />
                <span className="truncate">{getProjectName(session.amplifiedDir)}</span>
              </Link>
            )}
          </div>
        ))}
      </div>

      {/* Desktop view: table layout */}
      <div className="hidden sm:block border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-2 text-sm font-medium">Session</th>
              <th className="text-left px-4 py-2 text-sm font-medium">Project</th>
              <th className="text-right px-4 py-2 text-sm font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {sortedSessions.map((session) => (
              <tr key={session.sessionId} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link
                    to={`/directories/sessions/${session.sessionId}`}
                    className="flex items-center gap-2 hover:text-primary"
                  >
                    {session.isUnread && (
                      <span className="w-2 h-2 bg-primary rounded-full" />
                    )}
                    <MessageSquare className="h-4 w-4 flex-shrink-0" />
                    <span className={session.isUnread ? "font-bold" : ""}>
                      {session.name ||
                        `Session ${new Date(session.createdAt).toLocaleDateString()}`}
                    </span>
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {session.amplifiedDir ? (
                    <Link
                      to={`/directories?path=${encodeURIComponent(session.amplifiedDir)}`}
                      className="flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
                    >
                      <FolderOpen className="h-4 w-4" />
                      <span className="truncate max-w-[200px]">
                        {getProjectName(session.amplifiedDir)}
                      </span>
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-sm text-muted-foreground whitespace-nowrap">
                  {formatRelativeTime(session.createdAt)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
