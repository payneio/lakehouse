import type { AmplifiedDirectory } from '@/types/api';
import { Edit, Folder, Info, Trash2 } from 'lucide-react';

interface DirectoryDetailsPanelProps {
  directory: AmplifiedDirectory;
  onEdit: () => void;
  onDelete: () => void;
}

export function DirectoryDetailsPanel({ directory, onEdit, onDelete }: DirectoryDetailsPanelProps) {
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <Folder className="h-5 w-5 mt-1 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <h2 className="text-2xl font-bold truncate">{directory.relative_path}</h2>
            <div className="flex items-center gap-2 mt-2">
              <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-xs rounded-md">
                <Info className="h-3 w-3" />
                Amplified
              </span>
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

      <div className="border rounded-lg p-4 space-y-4">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Metadata</h3>
          {directory.metadata?.name || directory.metadata?.description ? (
            <div className="space-y-2">
              {directory.metadata.name && (
                <div>
                  <div className="text-xs text-muted-foreground">Name</div>
                  <div className="text-sm">{directory.metadata.name as string}</div>
                </div>
              )}
              {directory.metadata.description && (
                <div>
                  <div className="text-xs text-muted-foreground">Description</div>
                  <div className="text-sm">{directory.metadata.description as string}</div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No description</div>
          )}
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Profile</h3>
          {directory.default_profile ? (
            <div className="text-sm font-mono">{directory.default_profile}</div>
          ) : (
            <div className="text-sm text-muted-foreground">No default profile</div>
          )}
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Timestamps</h3>
          <div className="space-y-2 text-sm">
            {directory.metadata?.created_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{formatDate(directory.metadata.created_at as string)}</span>
              </div>
            )}
            {directory.metadata?.last_used && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last used</span>
                <span>{formatDate(directory.metadata.last_used as string)}</span>
              </div>
            )}
          </div>
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Path</h3>
          <div className="text-xs font-mono bg-muted p-2 rounded break-all">
            {directory.path}
          </div>
        </div>
      </div>
    </div>
  );
}
