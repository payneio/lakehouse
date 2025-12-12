import type { AmplifiedDirectoryCreate } from '@/types/api';
import { Plus } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { useDirectories } from '../hooks/useDirectories';
import { CreateDirectoryDialog } from './CreateDirectoryDialog';
import { TreeNode } from './TreeNode';
import { buildDirectoryTree } from '../utils/treeUtils';
import type { TreeNode as TreeNodeType } from '../utils/treeUtils';

const STORAGE_KEY = 'amplifier_expanded_directories';

interface DirectoriesListProps {
  onSelectDirectory: (path: string) => void;
  selectedPath?: string;
  compact?: boolean;
  unreadCounts?: Record<string, number>;
}

export function DirectoriesList({
  onSelectDirectory,
  selectedPath,
  compact = false,
  unreadCounts = {}
}: DirectoriesListProps) {
  const { directories, isLoading, createDirectory } = useDirectories();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Initialize expandedPaths from sessionStorage
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const pathsArray = JSON.parse(stored) as string[];
        return new Set(pathsArray);
      }
    } catch (err) {
      console.error('Failed to load expanded paths from sessionStorage:', err);
    }
    return new Set();
  });

  // Save expandedPaths to sessionStorage whenever it changes
  useEffect(() => {
    try {
      const pathsArray = Array.from(expandedPaths);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pathsArray));
    } catch (err) {
      console.error('Failed to save expanded paths to sessionStorage:', err);
    }
  }, [expandedPaths]);

  const tree = useMemo(() => {
    const baseTree = buildDirectoryTree(directories);
    // Apply expanded state to the tree
    const applyExpansion = (nodes: TreeNodeType[]): TreeNodeType[] => {
      return nodes.map((node) => ({
        ...node,
        isExpanded: expandedPaths.has(node.fullPath),
        children: applyExpansion(node.children),
      }));
    };
    return applyExpansion(baseTree);
  }, [directories, expandedPaths]);

  const handleToggle = (path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const handleSelect = (path: string) => {
    onSelectDirectory(path);
  };

  const handleCreateDirectory = async (data: AmplifiedDirectoryCreate) => {
    setCreateError(null);
    try {
      await createDirectory.mutateAsync(data);
      setShowCreateDialog(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create directory');
    }
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading projects...</div>;
  }

  // Compact mode: just render the tree without header
  if (compact) {
    return (
      <>
        {directories.length === 0 ? (
          <div className="text-muted-foreground text-center py-4 text-sm">
            No projects found
          </div>
        ) : (
          <div className="space-y-0.5">
            {tree.map((node) => (
              <TreeNode
                key={node.fullPath}
                node={node}
                selectedPath={selectedPath || null}
                onToggle={handleToggle}
                onSelect={handleSelect}
                unreadCounts={unreadCounts}
              />
            ))}
          </div>
        )}
      </>
    );
  }

  // Full mode: render with header and create button
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Projects</h2>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="flex items-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 text-sm"
        >
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>

      {directories.length === 0 ? (
        <div className="text-muted-foreground text-center py-8">
          No amplified directories found
        </div>
      ) : (
        <div className="space-y-1">
          {tree.map((node) => (
            <TreeNode
              key={node.fullPath}
              node={node}
              selectedPath={selectedPath || null}
              onToggle={handleToggle}
              onSelect={handleSelect}
              unreadCounts={unreadCounts}
            />
          ))}
        </div>
      )}

      <CreateDirectoryDialog
        open={showCreateDialog}
        onClose={() => {
          setShowCreateDialog(false);
          setCreateError(null);
        }}
        onSubmit={handleCreateDirectory}
        isLoading={createDirectory.isPending}
        error={createError || undefined}
      />
    </div>
  );
}
