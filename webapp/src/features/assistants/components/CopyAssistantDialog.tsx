import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

interface CopyAssistantDialogProps {
  open: boolean;
  sourceAssistantName: string | null;
  sourceAssistantSource: 'user' | 'system' | null;
  onClose: () => void;
  onCopy: (newName: string) => void;
  isLoading?: boolean;
  error?: string | null;
}

export function CopyAssistantDialog({
  open,
  sourceAssistantName,
  sourceAssistantSource,
  onClose,
  onCopy,
  isLoading = false,
  error,
}: CopyAssistantDialogProps) {
  const [newName, setNewName] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateName = (name: string): string | null => {
    if (!name) {
      return 'Assistant name is required';
    }
    if (!/^[a-z0-9-]+$/.test(name)) {
      return 'Name must contain only lowercase letters, numbers, and hyphens';
    }
    if (name.length > 50) {
      return 'Name must be 50 characters or less';
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const error = validateName(newName);
    if (error) {
      setValidationError(error);
      return;
    }

    setValidationError(null);
    onCopy(newName);
  };

  const handleClose = () => {
    if (!isLoading) {
      setNewName('');
      setValidationError(null);
      onClose();
    }
  };

  if (!sourceAssistantName) return null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Copy Assistant</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Source</label>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm">{sourceAssistantName}</span>
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  sourceAssistantSource === 'user'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {sourceAssistantSource === 'user' ? 'User' : 'System'}
              </span>
            </div>
          </div>

          <div>
            <label htmlFor="newName" className="block text-sm font-medium mb-1">
              New Assistant Name
            </label>
            <input
              id="newName"
              type="text"
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                setValidationError(null);
              }}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="my-custom-assistant"
              disabled={isLoading}
              autoFocus
            />
            <p className="text-xs text-muted-foreground mt-1">
              Lowercase letters, numbers, and hyphens only
            </p>
          </div>

          <p className="text-sm text-muted-foreground">
            The new assistant will be created as an editable copy in your assistant store.
          </p>

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
              disabled={isLoading || !newName}
            >
              {isLoading ? 'Copying...' : 'Copy Assistant'}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
