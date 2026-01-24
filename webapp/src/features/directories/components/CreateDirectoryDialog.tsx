import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { listBundles } from '@/api/bundles';
import { DirectoryBrowser } from './DirectoryBrowser';
import type { ProjectCreate } from '@/types/api';

interface CreateDirectoryDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: ProjectCreate) => void;
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
  const { data: bundles = [] } = useQuery({
    queryKey: ['bundles'],
    queryFn: listBundles,
  });
  const [formData, setFormData] = useState({
    relative_path: '',
    default_bundle: '',
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

    const submitData: ProjectCreate = {
      relative_path: formData.relative_path.trim(),
      create_marker: true,
    };

    if (formData.default_bundle) {
      submitData.default_bundle = formData.default_bundle;
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
        default_bundle: '',
        name: '',
        description: '',
      });
      setValidationError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
        <DialogHeader className="shrink-0">
          <DialogTitle>Create Project</DialogTitle>
        </DialogHeader>

        <form id="create-directory-form" onSubmit={handleSubmit} className="space-y-4 overflow-y-auto flex-1 pr-2">
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

          {/* Default Bundle Field */}
          <div>
            <label htmlFor="default_bundle" className="block text-sm font-medium mb-1">
              Default Bundle
            </label>
            {bundles.length > 0 ? (
              <select
                id="default_bundle"
                value={formData.default_bundle}
                onChange={(e) => setFormData({ ...formData, default_bundle: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                disabled={isLoading}
              >
                <option value="">None (inherit from parent)</option>
                {bundles.map((bundle) => (
                  <option key={bundle.name} value={bundle.name}>
                    {bundle.name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="default_bundle"
                type="text"
                value={formData.default_bundle}
                onChange={(e) => setFormData({ ...formData, default_bundle: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="bundle-name"
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

        </form>

        {/* Footer - outside form for sticky behavior, but still submits via form */}
        <DialogFooter className="shrink-0 pt-4 border-t mt-4">
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
            form="create-directory-form"
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? 'Creating...' : 'Create Directory'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
