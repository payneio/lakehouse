import { useState } from 'react';
import { X } from 'lucide-react';
import { useCreateRegistry } from '../hooks/useRegistries';

interface RegistryFormProps {
  isOpen: boolean;
  onClose: () => void;
}

export function RegistryForm({ isOpen, onClose }: RegistryFormProps) {
  const [uri, setUri] = useState('');
  const [description, setDescription] = useState('');
  const createMutation = useCreateRegistry();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createMutation.mutateAsync({ uri, description });
      onClose();
    } catch (error) {
      alert(`Failed to create registry: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border rounded-lg p-6 max-w-md w-full">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Add Registry</h2>
          <button onClick={onClose} className="p-1 hover:bg-accent rounded">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              URI *
            </label>
            <input
              type="text"
              value={uri}
              onChange={(e) => setUri(e.target.value)}
              placeholder="git+https://github.com/org/repo@main"
              className="w-full px-3 py-2 border rounded-md"
              required
            />
            <p className="text-xs text-muted-foreground mt-1">
              Must start with git+, file://, http://, or https://
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded-md hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Adding...' : 'Add Registry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
