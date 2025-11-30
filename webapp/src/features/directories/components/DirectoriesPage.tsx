import { useEffect, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { DirectoriesList } from './DirectoriesList';
import { SessionsList } from './SessionsList';
import { DirectoryDetailsPanel } from './DirectoryDetailsPanel';
import { EditDirectoryDialog } from './EditDirectoryDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { useDirectories } from '../hooks/useDirectories';
import * as api from '@/api';
import type { AmplifiedDirectory } from '@/types/api';

export function DirectoriesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const selectedPath = searchParams.get('path') || undefined;

  const [showDetails, setShowDetails] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedDirectory, setSelectedDirectory] = useState<AmplifiedDirectory | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const { updateDirectory, deleteDirectory } = useDirectories();

  // Save current URL to sessionStorage for nav link persistence
  useEffect(() => {
    const fullPath = location.pathname + location.search;
    sessionStorage.setItem('lastDirectoriesUrl', fullPath);
  }, [location]);

  // Fetch directory details when showing details
  useEffect(() => {
    if (selectedPath && showDetails) {
      api.getDirectory(selectedPath)
        .then(setSelectedDirectory)
        .catch((err) => {
          console.error('Failed to fetch directory details:', err);
          setShowDetails(false);
        });
    }
  }, [selectedPath, showDetails]);

  const handleSelectDirectory = (path: string) => {
    setSearchParams({ path });
    setShowDetails(false);
  };

  const handleViewDetails = (path: string) => {
    setSearchParams({ path });
    setShowDetails(true);
  };

  const handleBackToSessions = () => {
    setShowDetails(false);
  };

  const handleEdit = () => {
    setShowEditDialog(true);
  };

  const handleEditSubmit = async (data: { name?: string; description?: string; default_profile?: string }) => {
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
      setUpdateError(err instanceof Error ? err.message : 'Failed to update directory');
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
      setShowDetails(false);
      setSearchParams({});
      setSelectedDirectory(null);
    } catch (err) {
      console.error('Failed to delete directory:', err);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">Projects</h1>
        <p className="text-muted-foreground">
          Projects are "amplified directories". Browse projects and manage chat sessions
        </p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        <DirectoriesList
          onSelectDirectory={handleSelectDirectory}
          onViewDetails={handleViewDetails}
          selectedPath={selectedPath}
        />

        {selectedPath && (
          <div className="space-y-4">
            {showDetails && selectedDirectory ? (
              <>
                <button
                  onClick={handleBackToSessions}
                  className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Back to Sessions
                </button>
                <DirectoryDetailsPanel
                  directory={selectedDirectory}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              </>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold">Sessions</h2>
                  <button
                    onClick={() => setShowDetails(true)}
                    className="text-sm text-primary hover:underline"
                  >
                    View Details
                  </button>
                </div>
                <SessionsList directoryPath={selectedPath} />
              </>
            )}
          </div>
        )}
      </div>

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
            <p>
              Are you sure you want to delete this directory?
            </p>
            <p className="text-sm text-muted-foreground">
              This will remove the amplified marker file. The directory itself will not be deleted.
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
              {deleteDirectory.isPending ? 'Deleting...' : 'Delete'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
