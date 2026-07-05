import { useQuery } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { getBundleSource } from '@/api/bundles';

interface BundleSourceDialogProps {
  bundleName: string | null;
  open: boolean;
  onClose: () => void;
}

export function BundleSourceDialog({ bundleName, open, onClose }: BundleSourceDialogProps) {
  const { data: source, isLoading, error } = useQuery({
    queryKey: ['bundle', bundleName, 'source'],
    queryFn: () => getBundleSource(bundleName!),
    enabled: !!bundleName && open,
  });

  if (!bundleName) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Bundle Source: {bundleName}</DialogTitle>
          {source && (
            <p className="text-xs text-muted-foreground">
              {source.path} ({source.format})
            </p>
          )}
        </DialogHeader>

        {isLoading ? (
          <div className="py-8 text-center text-muted-foreground">Loading source...</div>
        ) : error ? (
          <div className="py-8 text-center text-red-500">Failed to load bundle source</div>
        ) : source ? (
          <div className="flex-1 overflow-auto">
            <pre className="text-sm bg-muted text-foreground p-4 rounded overflow-x-auto font-mono whitespace-pre">
              {source.content}
            </pre>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
