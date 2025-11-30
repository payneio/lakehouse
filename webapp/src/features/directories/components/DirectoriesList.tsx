import type { AmplifiedDirectoryCreate } from '@/types/api';
import { Folder, Plus, Info } from 'lucide-react';
import { useState } from 'react';
import { useDirectories } from '../hooks/useDirectories';
import { CreateDirectoryDialog } from './CreateDirectoryDialog';

interface DirectoriesListProps {
  onSelectDirectory: (path: string) => void;
  onViewDetails: (path: string) => void;
  selectedPath?: string;
}

export function DirectoriesList({ onSelectDirectory, onViewDetails, selectedPath }: DirectoriesListProps) {
  const { directories, isLoading, createDirectory } = useDirectories();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreateDirectory = async (data: AmplifiedDirectoryCreate) => {
    setCreateError(null);
    try {
      await createDirectory.mutateAsync(data);
      setShowCreateDialog(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create directory');
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading projects...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Projects</h2>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm"
        >
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>

      {directories.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No amplified directories found
        </div>
      ) : (
        <div className="space-y-2">
          {directories.map((dir) => (
            <div
              key={dir.relative_path}
              className={`flex items-center gap-2 p-3 rounded-md transition-colors ${
                selectedPath === dir.relative_path
                  ? 'bg-primary/10 text-primary border border-primary'
                  : 'hover:bg-accent border border-transparent'
              }`}
            >
              <button
                onClick={() => onSelectDirectory(dir.relative_path)}
                className="flex items-center gap-3 min-w-0 flex-1 text-left"
              >
                <Folder className="h-4 w-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{dir.relative_path}</div>
                  {dir.default_profile && (
                    <div className="text-xs text-muted-foreground truncate">
                      Profile: {dir.default_profile}
                    </div>
                  )}
                </div>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onViewDetails(dir.relative_path);
                }}
                className="p-2 hover:bg-accent rounded-md shrink-0"
                title="View details"
              >
                <Info className="h-4 w-4" />
              </button>
            </div>
          ))}
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
    </div>
  );
}
