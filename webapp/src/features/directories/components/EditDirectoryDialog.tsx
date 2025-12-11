import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import * as api from '@/api/profiles';
import type { AmplifiedDirectory } from '@/types/api';

interface EditDirectoryDialogProps {
  open: boolean;
  directory: AmplifiedDirectory | null;
  onClose: () => void;
  onSubmit: (data: { name?: string; description?: string; default_profile?: string }) => void;
  isLoading?: boolean;
  error?: string;
}

export function EditDirectoryDialog({
  open,
  directory,
  onClose,
  onSubmit,
  isLoading = false,
  error,
}: EditDirectoryDialogProps) {
  const { data: profiles = [] } = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
  });

  if (!directory) {
    return null;
  }

  // Use key prop to reset form state when directory changes
  return (
    <EditDirectoryForm
      key={directory.relative_path}
      open={open}
      directory={directory}
      profiles={profiles}
      onClose={onClose}
      onSubmit={onSubmit}
      isLoading={isLoading}
      error={error}
    />
  );
}

function EditDirectoryForm({
  open,
  directory,
  profiles,
  onClose,
  onSubmit,
  isLoading,
  error,
}: {
  open: boolean;
  directory: AmplifiedDirectory;
  profiles: Array<{ name: string }>;
  onClose: () => void;
  onSubmit: (data: { name?: string; description?: string; default_profile?: string }) => void;
  isLoading: boolean;
  error?: string;
}) {
  const [formData, setFormData] = useState({
    name: (directory?.metadata?.name as string) || '',
    description: (directory?.metadata?.description as string) || '',
    default_profile: directory?.default_profile || '',
  });
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateForm = (): string | null => {
    if (formData.name.length > 100) {
      return 'Name must be 100 characters or less';
    }
    if (formData.description.length > 500) {
      return 'Description must be 500 characters or less';
    }
    if (formData.default_profile) {
      // Build list of valid profile identifiers
      const validProfileIds = profiles.map(p => p.name);
      if (!validProfileIds.includes(formData.default_profile)) {
        return 'Invalid profile selection';
      }
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const validationErr = validateForm();
    if (validationErr) {
      setValidationError(validationErr);
      return;
    }

    setValidationError(null);

    const submitData: { name?: string; description?: string; default_profile?: string } = {};

    if (formData.name) {
      submitData.name = formData.name.trim();
    }
    if (formData.description) {
      submitData.description = formData.description.trim();
    }
    if (formData.default_profile) {
      submitData.default_profile = formData.default_profile;
    }

    onSubmit(submitData);
  };

  const handleClose = () => {
    if (!isLoading) {
      setValidationError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit Directory</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Directory Path (Read-only for context) */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Directory Path
            </label>
            <div className="w-full px-3 py-2 border rounded-md bg-muted text-muted-foreground">
              {directory.relative_path}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Path cannot be changed
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
                onChange={(e) => {
                  setFormData({ ...formData, default_profile: e.target.value });
                  setValidationError(null);
                }}
                className="w-full px-3 py-2 border rounded-md"
                disabled={isLoading}
              >
                <option value="">None (inherit from parent)</option>
                {profiles.map((profile) => (
                  <option key={profile.name} value={profile.name}>
                    {profile.name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="default_profile"
                type="text"
                value={formData.default_profile}
                onChange={(e) => {
                  setFormData({ ...formData, default_profile: e.target.value });
                  setValidationError(null);
                }}
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
              onChange={(e) => {
                setFormData({ ...formData, name: e.target.value });
                setValidationError(null);
              }}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="My Application"
              maxLength={100}
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Optional human-readable name (max 100 characters)
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
              onChange={(e) => {
                setFormData({ ...formData, description: e.target.value });
                setValidationError(null);
              }}
              className="w-full px-3 py-2 border rounded-md min-h-[80px]"
              placeholder="Describe this directory..."
              maxLength={500}
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Optional description (max 500 characters)
            </p>
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
              {isLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
