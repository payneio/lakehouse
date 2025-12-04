import { fetchApi } from "@/api/client";
import type { AmplifiedDirectory } from "@/types/api";
import { ChevronDown, ChevronRight, Edit, Folder, Trash2 } from "lucide-react";
import { useState } from "react";

interface DirectoryDetailsPanelProps {
  directory: AmplifiedDirectory;
  onEdit: () => void;
  onDelete: () => void;
}

export function DirectoryDetailsPanel({
  directory,
  onEdit,
  onDelete,
}: DirectoryDetailsPanelProps) {
  const formatDate = (dateString?: string) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  };

  // State for collapsible sections
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false);

  // State for editing agents content
  const [isEditingAgents, setIsEditingAgents] = useState(false);
  const [editedAgentsContent, setEditedAgentsContent] = useState("");
  const [displayedAgentsContent, setDisplayedAgentsContent] = useState(
    directory.agents_content || ""
  );
  const [agentsSaveStatus, setAgentsSaveStatus] = useState<
    "idle" | "saving" | "success" | "error"
  >("idle");
  const [agentsSaveError, setAgentsSaveError] = useState<string | null>(null);

  const handleSaveAgentsContent = async () => {
    if (!editedAgentsContent.trim()) {
      setAgentsSaveError("Content cannot be empty");
      return;
    }

    setAgentsSaveStatus("saving");
    setAgentsSaveError(null);

    try {
      // Use special /root/agents endpoint for root directory
      const isRoot =
        !directory.relative_path || directory.relative_path === ".";
      const endpoint = isRoot
        ? "/api/v1/amplified-directories/root/agents"
        : `/api/v1/amplified-directories/${encodeURIComponent(
            directory.relative_path
          )}/agents`;

      await fetchApi(endpoint, {
        method: "PUT",
        body: JSON.stringify({ content: editedAgentsContent }),
      });

      // Update displayed content immediately (triggers re-render)
      setDisplayedAgentsContent(editedAgentsContent);

      setAgentsSaveStatus("success");
      setIsEditingAgents(false);

      // Clear success message after 3 seconds
      setTimeout(() => setAgentsSaveStatus("idle"), 3000);
    } catch (error) {
      setAgentsSaveStatus("error");
      setAgentsSaveError(
        error instanceof Error ? error.message : "Failed to save"
      );
    }
  };

  const handleCancelAgentsEdit = () => {
    setIsEditingAgents(false);
    setEditedAgentsContent("");
    setAgentsSaveError(null);
    setAgentsSaveStatus("idle");
  };

  const handleStartAgentsEdit = () => {
    setEditedAgentsContent(displayedAgentsContent);
    setIsEditingAgents(true);
    setAgentsSaveError(null);
    setAgentsSaveStatus("idle");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <Folder className="h-5 w-5 mt-1 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <h2 className="text-2xl font-bold truncate">
              {directory.metadata?.name || directory.relative_path}
            </h2>
            <div className="text-sm text-muted-foreground font-mono mt-1 truncate">
              {directory.relative_path}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onEdit}
            className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent text-sm"
          >
            <Edit className="h-4 w-4" />
            Edit
          </button>
          <button
            onClick={onDelete}
            className="flex items-center gap-2 px-3 py-2 border border-destructive text-destructive rounded-md hover:bg-destructive/10 text-sm"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {directory.metadata?.description && (
        <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
          <div className="text-sm text-muted-foreground leading-relaxed">
            {directory.metadata.description as string}
          </div>
        </div>
      )}

      <div className="border rounded-lg p-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setIsMetadataExpanded(!isMetadataExpanded)}
            className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            {isMetadataExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            Project Details
          </button>
        </div>

        {isMetadataExpanded && (
          <div className="mt-4 space-y-4">
            <div className="">
              <h3 className="text-sm font-medium text-muted-foreground mb-2">
                Default Profile
              </h3>
              {directory.default_profile ? (
                <div className="text-sm font-mono">
                  {directory.default_profile}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  No default profile
                </div>
              )}
            </div>

            {directory.last_used_at && (
              <div className="border-t pt-4">
                <h3 className="text-sm font-medium text-muted-foreground mb-2">
                  Last Used
                </h3>
                <div className="text-sm">
                  {formatDate(directory.last_used_at)}
                </div>
              </div>
            )}

            {directory.agents_content !== undefined && (
              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Agent Instructions
                  </h3>
                  {!isEditingAgents && (
                    <button
                      onClick={handleStartAgentsEdit}
                      className="flex items-center gap-1 px-2 py-1 text-xs border rounded-md hover:bg-accent"
                    >
                      <Edit className="h-3 w-3" />
                      Edit
                    </button>
                  )}
                </div>

                {isEditingAgents ? (
                  <div className="space-y-3">
                    <textarea
                      value={editedAgentsContent}
                      onChange={(e) => setEditedAgentsContent(e.target.value)}
                      className="w-full min-h-[300px] p-3 font-mono text-xs border rounded-md bg-muted resize-y"
                      placeholder="Enter agent instructions..."
                    />

                    {agentsSaveError && (
                      <div className="text-sm text-destructive bg-destructive/10 p-2 rounded-md">
                        {agentsSaveError}
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleSaveAgentsContent}
                        disabled={agentsSaveStatus === "saving"}
                        className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 text-sm"
                      >
                        {agentsSaveStatus === "saving" ? "Saving..." : "Save"}
                      </button>
                      <button
                        onClick={handleCancelAgentsEdit}
                        disabled={agentsSaveStatus === "saving"}
                        className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent disabled:opacity-50 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {agentsSaveStatus === "success" && (
                      <div className="mb-3 text-sm text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950 p-2 rounded-md">
                        Changes saved successfully
                      </div>
                    )}
                    <div className="prose prose-sm max-w-none dark:prose-invert bg-muted p-4 rounded-md overflow-auto max-h-96">
                      <pre className="whitespace-pre-wrap font-mono text-xs">
                        {displayedAgentsContent ||
                          "No agent instructions defined"}
                      </pre>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
