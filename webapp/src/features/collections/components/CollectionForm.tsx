import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface CollectionFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (data: { identifier: string; source: string }) => void;
}

export function CollectionForm({ isOpen, onClose, onSuccess }: CollectionFormProps) {
  const [formData, setFormData] = useState({
    identifier: '',
    source: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSuccess(formData);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Mount Collection</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Identifier</label>
            <input
              type="text"
              value={formData.identifier}
              onChange={(e) => setFormData({ ...formData, identifier: e.target.value })}
              pattern="^[a-z0-9-]+$"
              className="w-full px-3 py-2 border rounded-md"
              required
              placeholder="my-collection"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Lowercase letters, numbers, and hyphens only (e.g., "my-profiles")
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Source</label>
            <input
              type="text"
              value={formData.source}
              onChange={(e) => setFormData({ ...formData, source: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              required
              placeholder="git+https://github.com/user/repo or /path/to/dir"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Git URL (git+https://...) or local path (/path/to/dir)
            </p>
          </div>

          <div className="flex gap-2 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded-md hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Mount Collection
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
