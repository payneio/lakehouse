import { useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronRight } from 'lucide-react';
import { useRegistries, useDeleteRegistry } from '../hooks/useRegistries';
import { RegistryForm } from './RegistryForm';

export function RegistryManager() {
  const { data: registries = [], isLoading } = useRegistries();
  const deleteRegistryMutation = useDeleteRegistry();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isAddingRegistry, setIsAddingRegistry] = useState(false);

  const handleDelete = (id: string) => {
    if (id === 'lakehouse') {
      alert('Cannot delete the default lakehouse registry');
      return;
    }
    if (confirm(`Delete registry "${id}"?`)) {
      deleteRegistryMutation.mutate(id);
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading registries...</div>;
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-4 hover:bg-accent transition-colors">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 flex-1"
        >
          {isExpanded ? (
            <ChevronDown className="h-5 w-5" />
          ) : (
            <ChevronRight className="h-5 w-5" />
          )}
          <h3 className="font-semibold">Registries</h3>
          <span className="text-sm text-muted-foreground">
            ({registries.length})
          </span>
        </button>
        <button
          onClick={() => setIsAddingRegistry(true)}
          className="flex items-center gap-1 sm:gap-2 px-2 py-1.5 sm:px-3 border rounded-md hover:bg-background text-sm"
          title="Add Registry"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Add Registry</span>
        </button>
      </div>

      {isExpanded && (
        <div className="border-t p-4 space-y-2">
          {registries.map((registry) => (
            <div
              key={registry.id}
              className="flex items-start justify-between p-3 border rounded-md hover:bg-accent/50"
            >
              <div className="flex-1">
                <div className="font-medium">{registry.id}</div>
                <div className="text-sm text-muted-foreground truncate">
                  {registry.uri}
                </div>
                {registry.description && (
                  <div className="text-xs text-muted-foreground mt-1">
                    {registry.description}
                  </div>
                )}
              </div>
              {registry.id !== 'lakehouse' && (
                <button
                  onClick={() => handleDelete(registry.id)}
                  className="p-1.5 hover:bg-background rounded-md text-destructive"
                  title="Delete registry"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {isAddingRegistry && (
        <RegistryForm
          isOpen={isAddingRegistry}
          onClose={() => setIsAddingRegistry(false)}
        />
      )}
    </div>
  );
}
