import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertCircle } from 'lucide-react';
import { copyProfile } from '@/api/profiles';

interface CopyProfileDialogProps {
  sourceName: string | null;
  onClose: () => void;
  onSuccess?: () => void;
}

export function CopyProfileDialog({ sourceName, onClose, onSuccess }: CopyProfileDialogProps) {
  const [newName, setNewName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const copyMutation = useMutation({
    mutationFn: ({ sourceName, newName }: { sourceName: string; newName: string }) =>
      copyProfile(sourceName, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      // Invalidate all profile details to ensure fresh data
      queryClient.invalidateQueries({ queryKey: ['profile-detail'] });
      if (onSuccess) onSuccess();
    },
  });

  if (!sourceName) return null;

  const validateName = (name: string): string | null => {
    if (!name) {
      return 'Profile name is required';
    }
    if (!/^[a-z0-9-]+$/.test(name)) {
      return 'Name must contain only lowercase letters, numbers, and hyphens';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validationError = validateName(newName);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await copyMutation.mutateAsync({
        sourceName: sourceName,
        newName: newName.trim(),
      });
      setNewName('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to copy profile');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setNewName('');
      setError(null);
      onClose();
    }
  };

  return (
    <Dialog open={!!sourceName} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Copy Profile</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="source-name" className="block text-sm font-medium mb-1">
              Source Profile
            </label>
            <div className="w-full px-3 py-2 border rounded-md bg-muted text-muted-foreground">
              {sourceName}
            </div>
          </div>

          <div>
            <label htmlFor="new-name" className="block text-sm font-medium mb-1">
              New Profile Name
            </label>
            <input
              id="new-name"
              type="text"
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                setError(null);
              }}
              onBlur={() => {
                if (newName) {
                  const validationError = validateName(newName);
                  if (validationError) {
                    setError(validationError);
                  }
                }
              }}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="my-custom-profile"
              disabled={isSubmitting}
              autoFocus
            />
            <p className="text-xs text-muted-foreground mt-1">
              Use lowercase letters, numbers, and hyphens only
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="text-destructive">{error}</div>
            </div>
          )}

          <DialogFooter>
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 border rounded-md hover:bg-accent"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              disabled={isSubmitting || !newName}
            >
              {isSubmitting ? 'Copying...' : 'Copy Profile'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
