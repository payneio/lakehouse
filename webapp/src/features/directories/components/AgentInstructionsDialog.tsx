import { fetchApi } from "@/api/client";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { AmplifiedDirectory } from "@/types/api";
import { useState } from "react";

interface AgentInstructionsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  directory: AmplifiedDirectory;
  onSaveSuccess?: () => void;
}

function AgentInstructionsForm({
  directory,
  onClose,
  onSaveSuccess,
}: {
  directory: AmplifiedDirectory;
  onClose: () => void;
  onSaveSuccess?: () => void;
}) {
  const [editedContent, setEditedContent] = useState(
    directory.agents_content || ""
  );
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "success" | "error"
  >("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!editedContent.trim()) {
      setSaveError("Content cannot be empty");
      return;
    }

    setSaveStatus("saving");
    setSaveError(null);

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
        body: JSON.stringify({ content: editedContent }),
      });

      setSaveStatus("success");
      onSaveSuccess?.(); // Notify parent to refetch directory data

      // Auto-close after successful save
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (error) {
      setSaveStatus("error");
      setSaveError(error instanceof Error ? error.message : "Failed to save");
    }
  };

  const handleCancel = () => {
    onClose();
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>Project Instructions</DialogTitle>
      </DialogHeader>

      <div className="space-y-3">
        <textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          className="w-full min-h-[400px] p-3 font-mono text-xs border rounded-md bg-muted resize-y"
          placeholder="Enter project instructions for the assistant..."
        />

        {saveStatus === "success" && (
          <div className="text-sm text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950 p-2 rounded-md">
            Changes saved successfully
          </div>
        )}

        {saveError && (
          <div className="text-sm text-destructive bg-destructive/10 p-2 rounded-md">
            {saveError}
          </div>
        )}
      </div>

      <DialogFooter>
        <button
          onClick={handleCancel}
          disabled={saveStatus === "saving"}
          className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent disabled:opacity-50 text-sm"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saveStatus === "saving"}
          className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 text-sm"
        >
          {saveStatus === "saving" ? "Saving..." : "Save"}
        </button>
      </DialogFooter>
    </>
  );
}

export function AgentInstructionsDialog({
  open,
  onOpenChange,
  directory,
  onSaveSuccess,
}: AgentInstructionsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        {/* Use key to reset form state when directory changes */}
        {open && (
          <AgentInstructionsForm
            key={directory.relative_path}
            directory={directory}
            onClose={() => onOpenChange(false)}
            onSaveSuccess={onSaveSuccess}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
