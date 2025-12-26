import * as api from "@/api";
import { listAutomations } from "@/api/automations";
import { MobileMenuButton } from "@/components/layout/MobileMenuButton";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { AmplifiedDirectory, AmplifiedDirectoryCreate } from "@/types/api";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, FileText, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDirectories } from "../hooks/useDirectories";
import { AgentInstructionsDialog } from "./AgentInstructionsDialog";
import { AutomationsSection } from "./AutomationsSection";
import { CreateDirectoryDialog } from "./CreateDirectoryDialog";
import { EditDirectoryDialog } from "./EditDirectoryDialog";
import { RecentSessionsTable } from "./RecentSessionsTable";
import { SessionsList } from "./SessionsList";
import { WorkSection } from "./WorkSection";

export function DirectoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedPath = searchParams.get("path") || undefined;

  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showAgentInstructions, setShowAgentInstructions] = useState(false);
  const [showAutomations, setShowAutomations] = useState(false);
  const [showWork, setShowWork] = useState(false);
  const [selectedDirectory, setSelectedDirectory] =
    useState<AmplifiedDirectory | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [isFetchingDetails, setIsFetchingDetails] = useState(false);

  const { updateDirectory, deleteDirectory, createDirectory } =
    useDirectories();

  // Fetch enabled automations count for badge
  const { data: automationsData } = useQuery({
    queryKey: ["automations", selectedPath, "enabled"],
    queryFn: () => listAutomations(selectedPath!, { enabled: true }),
    enabled: !!selectedPath,
  });

  const enabledAutomationsCount = automationsData?.automations?.length || 0;

  // Fetch directory details when path is selected
  useEffect(() => {
    let cancelled = false;

    if (selectedPath) {
      const fetchDetails = async () => {
        setIsFetchingDetails(true);
        try {
          const directory = await api.getDirectory(selectedPath);
          if (!cancelled) {
            setSelectedDirectory(directory);
          }
        } catch (err) {
          if (!cancelled) {
            console.error("Failed to fetch directory details:", err);
          }
        } finally {
          if (!cancelled) {
            setIsFetchingDetails(false);
          }
        }
      };

      void fetchDetails();
    } else {
      setSelectedDirectory(null);
    }

    return () => {
      cancelled = true;
    };
  }, [selectedPath]);

  const handleEdit = () => {
    setShowEditDialog(true);
  };

  const handleEditSubmit = async (data: {
    name?: string;
    description?: string;
    default_profile?: string;
  }) => {
    if (!selectedPath) return;

    setUpdateError(null);
    try {
      // All fields go into metadata (default_profile is stored in metadata.json)
      const metadata: Record<string, unknown> = {
        ...selectedDirectory?.metadata,
      };

      // Update only the fields that were provided
      if (data.name !== undefined) {
        metadata.name = data.name.trim();
      }
      if (data.description !== undefined) {
        metadata.description = data.description.trim();
      }
      if (data.default_profile !== undefined) {
        metadata.default_profile = data.default_profile;
      }

      // Update directory - mutation returns updated directory
      const updated = await updateDirectory.mutateAsync({
        relativePath: selectedPath,
        data: { metadata },
      });

      // Use the returned updated directory (no need for separate GET)
      setSelectedDirectory(updated);
      setShowEditDialog(false);
    } catch (err) {
      setUpdateError(
        err instanceof Error ? err.message : "Failed to update directory"
      );
    }
  };

  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedPath) return;

    try {
      await deleteDirectory.mutateAsync({
        relativePath: selectedPath,
        removeMarker: true,
      });
      setShowDeleteConfirm(false);
      setSearchParams({});
      setSelectedDirectory(null);
    } catch (err) {
      console.error("Failed to delete directory:", err);
    }
  };

  const handleCreateDirectory = async (data: AmplifiedDirectoryCreate) => {
    setCreateError(null);
    try {
      await createDirectory.mutateAsync(data);
      setShowCreateDialog(false);
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create directory"
      );
    }
  };

  return (
    <div className="container mx-auto p-6">
      {selectedPath ? (
        <div className="space-y-8">
          {isFetchingDetails ? (
            <div className="flex items-center justify-center p-8">
              <div className="text-muted-foreground">
                Loading project details...
              </div>
            </div>
          ) : selectedDirectory ? (
            <div className="space-y-6">
              {/* Header with dialog buttons */}
              <div className="flex justify-between items-center gap-2">
                <div className="flex items-center gap-2">
                  <MobileMenuButton />
                  <h2 className="text-xl font-semibold">Project</h2>
                </div>
                <div className="flex gap-1 sm:gap-2 flex-wrap justify-end">
                  <button
                    onClick={handleEdit}
                    className="flex items-center gap-1 px-2 py-1.5 sm:px-3 sm:py-2 border rounded-md hover:bg-accent text-sm"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4 sm:hidden" />
                    <span className="hidden sm:inline">Edit</span>
                  </button>
                  <button
                    onClick={handleDelete}
                    className="flex items-center gap-1 px-2 py-1.5 sm:px-3 sm:py-2 border border-destructive text-destructive rounded-md hover:bg-destructive hover:text-destructive-foreground text-sm"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4 sm:hidden" />
                    <span className="hidden sm:inline">Delete</span>
                  </button>
                </div>
              </div>

              {/* Project name and description */}
              <div>
                <h1 className="text-2xl font-bold">
                  {(selectedDirectory.metadata?.name as string) || selectedPath?.split("/").pop() || "Untitled Project"}
                </h1>
                {selectedDirectory.metadata?.description && (
                  <p className="text-muted-foreground mt-1">
                    {selectedDirectory.metadata.description as string}
                  </p>
                )}
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                  {selectedPath}
                </p>
              </div>

              {/* Project Actions */}
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => setShowAgentInstructions(true)}
                  className="flex items-center gap-1 px-3 py-2 border rounded-md hover:bg-accent text-sm"
                >
                  <FileText className="h-4 w-4" />
                  <span>Instructions</span>
                </button>
                <button
                  onClick={() => setShowAutomations(true)}
                  className="flex items-center gap-1 px-3 py-2 border rounded-md hover:bg-accent text-sm relative"
                >
                  <Clock className="h-4 w-4" />
                  <span>Automations</span>
                  {enabledAutomationsCount > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 text-xs bg-primary text-primary-foreground rounded-full">
                      {enabledAutomationsCount}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setShowWork(true)}
                  className="flex items-center gap-1 px-3 py-2 border rounded-md hover:bg-accent text-sm relative"
                >
                  <Activity className="h-4 w-4" />
                  <span>Work</span>
                  <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center font-medium">
                    2
                  </span>
                </button>
              </div>

              {/* Chat Sessions */}
              <SessionsList directoryPath={selectedPath} />
            </div>
          ) : null}
        </div>
      ) : (
        <div className="max-w-3xl mx-auto">
          <div className="py-8 space-y-8">
            <div className="flex items-center gap-3">
              <MobileMenuButton />
              <div>
                <h1 className="text-3xl font-bold mb-2">Projects Dashboard</h1>
                <p className="text-muted-foreground">
                  Manage your amplified directories and chat sessions
                </p>
              </div>
            </div>
            <div className="flex justify-center">
              <button
                onClick={() => setShowCreateDialog(true)}
                className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 font-medium"
              >
                <Plus className="h-5 w-5" />
                Add Project
              </button>
            </div>

            {/* Recent Sessions */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Recent Sessions</h2>
              <RecentSessionsTable />
            </div>
          </div>
        </div>
      )}

      <CreateDirectoryDialog
        open={showCreateDialog}
        onClose={() => {
          setShowCreateDialog(false);
          setCreateError(null);
        }}
        onSubmit={handleCreateDirectory}
        isLoading={createDirectory.isPending}
        error={createError || undefined}
      />

      <EditDirectoryDialog
        open={showEditDialog}
        directory={selectedDirectory}
        onClose={() => {
          setShowEditDialog(false);
          setUpdateError(null);
        }}
        onSubmit={handleEditSubmit}
        isLoading={updateDirectory.isPending}
        error={updateError || undefined}
      />

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Directory</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>Are you sure you want to delete this directory?</p>
            <p className="text-sm text-muted-foreground">
              This will remove the amplified marker file. The directory itself
              will not be deleted.
            </p>
          </div>
          <DialogFooter>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              className="px-4 py-2 border rounded-md hover:bg-accent"
              disabled={deleteDirectory.isPending}
            >
              Cancel
            </button>
            <button
              onClick={handleDeleteConfirm}
              className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 disabled:opacity-50"
              disabled={deleteDirectory.isPending}
            >
              {deleteDirectory.isPending ? "Deleting..." : "Delete"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {selectedDirectory && (
        <>
          <AgentInstructionsDialog
            open={showAgentInstructions}
            onOpenChange={setShowAgentInstructions}
            directory={selectedDirectory}
            onSaveSuccess={async () => {
              if (selectedPath) {
                const updated = await api.getDirectory(selectedPath);
                setSelectedDirectory(updated);
              }
            }}
          />

          <Dialog open={showAutomations} onOpenChange={setShowAutomations}>
            <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Automations</DialogTitle>
              </DialogHeader>
              <AutomationsSection projectId={selectedPath!} />
            </DialogContent>
          </Dialog>

          <Dialog open={showWork} onOpenChange={setShowWork}>
            <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Work (7)</DialogTitle>
              </DialogHeader>
              <WorkSection directoryPath={selectedPath!} />
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  );
}
