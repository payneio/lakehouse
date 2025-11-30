import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertCircle } from 'lucide-react';
import { useProfiles } from '@/features/collections/hooks/useCollections';
import { DirectoryBrowser } from './DirectoryBrowser';
import type { AmplifiedDirectoryCreate } from '@/types/api';

interface CreateDirectoryDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: AmplifiedDirectoryCreate) => void;
  isLoading?: boolean;
  error?: string;
}

export function CreateDirectoryDialog({
  open,
  onClose,
  onSubmit,
  isLoading = false,
  error,
}: CreateDirectoryDialogProps) {
  const { profiles } = useProfiles();
  const [formData, setFormData] = useState({
    relative_path: '',
    default_profile: '',
    name: '',
    description: '',
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  const validatePath = (path: string): string | null => {
    if (!path.trim()) {
      return 'Please enter a directory path';
    }
    if (path.startsWith('/')) {
      return 'Path must be relative (don\'t start with /)';
    }
    if (path.includes('..')) {
      return 'Path cannot contain ..';
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const pathError = validatePath(formData.relative_path);
    if (pathError) {
      setValidationError(pathError);
      return;
    }

    setValidationError(null);

    const submitData: AmplifiedDirectoryCreate = {
      relative_path: formData.relative_path.trim(),
      create_marker: true,
    };

    if (formData.default_profile) {
      submitData.default_profile = formData.default_profile;
    }

    const metadata: Record<string, unknown> = {};
    if (formData.name) {
      metadata.name = formData.name;
    }
    if (formData.description) {
      metadata.description = formData.description;
    }
    if (Object.keys(metadata).length > 0) {
      submitData.metadata = metadata;
    }

    onSubmit(submitData);
  };

  const handleClose = () => {
    if (!isLoading) {
      setFormData({
        relative_path: '',
        default_profile: '',
        name: '',
        description: '',
      });
      setValidationError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create Amplified Directory</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Path Field */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Directory Path <span className="text-destructive">*</span>
            </label>
            <DirectoryBrowser
              initialPath=""
              onSelect={(path) => {
                setFormData({ ...formData, relative_path: path });
                setValidationError(null);
              }}
              allowCreate={true}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Browse or create a directory in your workspace
            </p>
          </div>

          {/* Default Profile Field */}
          <div>
            <label htmlFor="default_profile" className="block text-sm font-medium mb-1">
              Default Profile
            </label>
            {profiles.length > 0 ? (
              <select
                id="default_profile"
                value={formData.default_profile}
                onChange={(e) => setFormData({ ...formData, default_profile: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                disabled={isLoading}
              >
                <option value="">None (inherit from parent)</option>
                {profiles.map((profile) => {
                  const fullName = profile.collectionId
                    ? `${profile.collectionId}/${profile.name}`
                    : profile.name;
                  return (
                    <option key={fullName} value={fullName}>
                      {fullName}
                    </option>
                  );
                })}
              </select>
            ) : (
              <input
                id="default_profile"
                type="text"
                value={formData.default_profile}
                onChange={(e) => setFormData({ ...formData, default_profile: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="profile-name"
                disabled={isLoading}
              />
            )}
            <p className="text-xs text-muted-foreground mt-1">
              If not specified, will inherit from parent directory
            </p>
          </div>

          {/* Name Field */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-1">
              Name
            </label>
            <input
              id="name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="My Application"
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Optional human-readable name
            </p>
          </div>

          {/* Description Field */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium mb-1">
              Description
            </label>
            <textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 border rounded-md min-h-[80px]"
              placeholder="Describe this directory..."
              disabled={isLoading}
            />
          </div>

          {/* Error Messages */}
          {(validationError || error) && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="text-destructive">{validationError || error}</div>
            </div>
          )}

          {/* Footer */}
          <DialogFooter>
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 border rounded-md hover:bg-accent"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              disabled={isLoading}
            >
              {isLoading ? 'Creating...' : 'Create Directory'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
