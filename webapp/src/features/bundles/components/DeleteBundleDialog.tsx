import { AlertCircle, Trash2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

interface DeleteBundleDialogProps {
  open: boolean;
  bundleName: string | null;
  bundleSource?: 'user' | 'system' | null;
  onClose: () => void;
  onDelete: () => void;
  isLoading?: boolean;
  error?: string | null;
}

export function DeleteBundleDialog({
  open,
  bundleName,
  bundleSource = 'user',
  onClose,
  onDelete,
  isLoading = false,
  error,
}: DeleteBundleDialogProps) {
  const handleClose = () => {
    if (!isLoading) {
      onClose();
    }
  };

  if (!bundleName) return null;

  const isUserBundle = bundleSource === 'user';
  const title = isUserBundle ? 'Delete Bundle' : 'Remove Bundle';
  const actionLabel = isUserBundle ? 'Delete Bundle' : 'Remove Bundle';
  const loadingLabel = isUserBundle ? 'Deleting...' : 'Removing...';

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <Trash2 className="h-5 w-5" />
            {title}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <p className="text-sm">
            Are you sure you want to {isUserBundle ? 'delete' : 'remove'} the bundle{' '}
            <code className="bg-gray-100 px-1 rounded font-mono">{bundleName}</code>?
          </p>
          <p className="text-sm text-muted-foreground">
            {isUserBundle ? (
              <>
                This action cannot be undone. The bundle file will be permanently removed from your user
                bundles folder.
              </>
            ) : (
              <>
                This will remove the bundle from your registry (BUNDLES.txt). The cached files will remain
                but the bundle will no longer be available. You can re-add it later using the git URL.
              </>
            )}
          </p>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="text-destructive">{error}</div>
            </div>
          )}
        </div>

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
            type="button"
            onClick={onDelete}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? loadingLabel : actionLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
