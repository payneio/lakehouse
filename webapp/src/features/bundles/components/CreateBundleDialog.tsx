import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import type { BundleListItem } from '@/api/bundles';

interface CreateBundleDialogProps {
  open: boolean;
  bundles: BundleListItem[];
  onClose: () => void;
  onCreate: (data: { name: string; baseBundle?: string; description?: string }) => void;
  isLoading?: boolean;
  error?: string | null;
}

export function CreateBundleDialog({
  open,
  bundles,
  onClose,
  onCreate,
  isLoading = false,
  error,
}: CreateBundleDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [baseBundle, setBaseBundle] = useState<string>('');
  const [startFromExisting, setStartFromExisting] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateForm = (): string | null => {
    if (!name) {
      return 'Bundle name is required';
    }
    if (!/^[a-z0-9-]+$/.test(name)) {
      return 'Name must contain only lowercase letters, numbers, and hyphens';
    }
    if (name.length > 50) {
      return 'Name must be 50 characters or less';
    }
    if (bundles.some((b) => b.name === name)) {
      return 'A bundle with this name already exists';
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const error = validateForm();
    if (error) {
      setValidationError(error);
      return;
    }

    setValidationError(null);
    onCreate({
      name,
      baseBundle: startFromExisting && baseBundle ? baseBundle : undefined,
      description: description || undefined,
    });
  };

  const handleClose = () => {
    if (!isLoading) {
      setName('');
      setDescription('');
      setBaseBundle('');
      setStartFromExisting(true);
      setValidationError(null);
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Bundle</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Start From Option */}
          <div>
            <label className="block text-sm font-medium mb-2">Start from</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={startFromExisting}
                  onChange={() => setStartFromExisting(true)}
                  disabled={isLoading}
                />
                <span className="text-sm">Existing bundle</span>
              </label>
              {startFromExisting && (
                <select
                  value={baseBundle}
                  onChange={(e) => setBaseBundle(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md ml-6"
                  disabled={isLoading}
                >
                  <option value="">Select a bundle...</option>
                  {bundles.map((bundle) => (
                    <option key={bundle.name} value={bundle.name}>
                      {bundle.name} ({bundle.source})
                    </option>
                  ))}
                </select>
              )}
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={!startFromExisting}
                  onChange={() => setStartFromExisting(false)}
                  disabled={isLoading}
                />
                <span className="text-sm">Blank (minimal bundle)</span>
              </label>
            </div>
          </div>

          {/* Bundle Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-1">
              Bundle Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setValidationError(null);
              }}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="my-new-bundle"
              disabled={isLoading}
              autoFocus
            />
            <p className="text-xs text-muted-foreground mt-1">
              Lowercase letters, numbers, and hyphens only
            </p>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium mb-1">
              Description
            </label>
            <input
              id="description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="My custom development bundle"
              disabled={isLoading}
            />
          </div>

          {(validationError || error) && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="text-destructive">{validationError || error}</div>
            </div>
          )}

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
              disabled={isLoading || !name}
            >
              {isLoading ? 'Creating...' : 'Create Bundle'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
