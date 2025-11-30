import { useState, useEffect } from 'react';
import { AlertCircle, Folder, ChevronUp, Plus, Loader2 } from 'lucide-react';
import { listDirectoryContents, createDirectoryPath } from '@/api/directories';
import type { DirectoryListResponse } from '@/types/api';

interface DirectoryBrowserProps {
  initialPath?: string;
  onSelect: (path: string) => void;
  allowCreate?: boolean;
}

export function DirectoryBrowser({
  initialPath = '',
  onSelect,
  allowCreate = false,
}: DirectoryBrowserProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [directories, setDirectories] = useState<string[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingNew, setCreatingNew] = useState(false);
  const [newDirName, setNewDirName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    loadDirectories(currentPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPath]);

  const loadDirectories = async (path: string) => {
    setLoading(true);
    setError(null);

    try {
      const response: DirectoryListResponse = await listDirectoryContents(path);
      setDirectories(response.directories);
      setParentPath(response.parent_path);
      onSelect(response.current_path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load directories');
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = (dirName: string) => {
    const newPath = currentPath ? `${currentPath}/${dirName}` : dirName;
    setCurrentPath(newPath);
  };

  const handleParentClick = () => {
    if (parentPath !== null) {
      setCurrentPath(parentPath);
    }
  };

  const validateDirName = (name: string): string | null => {
    if (!name.trim()) {
      return 'Directory name cannot be empty';
    }
    if (name.includes('/')) {
      return 'Directory name cannot contain /';
    }
    if (name.startsWith('.')) {
      return 'Directory name cannot start with .';
    }
    if (name.includes('..')) {
      return 'Directory name cannot contain ..';
    }
    return null;
  };

  const handleCreateDirectory = async () => {
    const validationError = validateDirName(newDirName);
    if (validationError) {
      setCreateError(validationError);
      return;
    }

    setLoading(true);
    setCreateError(null);

    try {
      const newPath = currentPath ? `${currentPath}/${newDirName}` : newDirName;
      await createDirectoryPath({ relative_path: newPath });

      setNewDirName('');
      setCreatingNew(false);

      await loadDirectories(currentPath);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create directory');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleCreateDirectory();
    } else if (e.key === 'Escape') {
      setCreatingNew(false);
      setNewDirName('');
      setCreateError(null);
    }
  };

  return (
    <div className="border rounded-md">
      {/* Current Path Header */}
      <div className="px-3 py-2 bg-gray-50 border-b">
        <div className="flex items-center gap-2 text-sm">
          <Folder className="h-4 w-4 text-gray-500" />
          <span className="font-mono text-gray-700">
            {currentPath || '/'}
          </span>
        </div>
      </div>

      {/* Directory List */}
      <div className="min-h-[200px] max-h-[400px] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        ) : error ? (
          <div className="p-4">
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-md text-sm">
              <AlertCircle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-800">{error}</p>
                <button
                  type="button"
                  onClick={() => loadDirectories(currentPath)}
                  className="mt-2 text-red-600 hover:text-red-800 underline text-xs"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="divide-y">
            {/* Parent Directory Button */}
            {parentPath !== null && (
              <button
                type="button"
                onClick={handleParentClick}
                className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-50 transition-colors text-left"
                aria-label="Go to parent directory"
              >
                <ChevronUp className="h-4 w-4 text-gray-500" />
                <span className="text-sm text-gray-700">..</span>
              </button>
            )}

            {/* Directory List */}
            {directories.length === 0 && !creatingNew ? (
              <div className="px-3 py-8 text-center text-sm text-gray-500">
                This directory is empty
              </div>
            ) : (
              directories.map((dir) => (
                <button
                  type="button"
                  key={dir}
                  onClick={() => handleNavigate(dir)}
                  className="w-full px-3 py-2 flex items-center gap-2 hover:bg-gray-50 transition-colors text-left"
                  aria-label={`Navigate to ${dir}`}
                >
                  <Folder className="h-4 w-4 text-blue-500" />
                  <span className="text-sm text-gray-900">{dir.split('/').pop()}</span>
                </button>
              ))
            )}

            {/* Create New Directory Input */}
            {creatingNew && (
              <div className="px-3 py-2 border-t">
                <div className="flex items-center gap-2">
                  <Folder className="h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    value={newDirName}
                    onChange={(e) => {
                      setNewDirName(e.target.value);
                      setCreateError(null);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder="New folder name"
                    className="flex-1 px-2 py-1 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    autoFocus
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={handleCreateDirectory}
                    disabled={loading}
                    className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:opacity-50"
                  >
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCreatingNew(false);
                      setNewDirName('');
                      setCreateError(null);
                    }}
                    disabled={loading}
                    className="px-2 py-1 border rounded text-xs hover:bg-gray-50 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
                {createError && (
                  <div className="mt-2 flex items-start gap-1 text-xs text-red-600">
                    <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                    <span>{createError}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create New Folder Button */}
      {allowCreate && !creatingNew && !loading && (
        <div className="px-3 py-2 border-t">
          <button
            type="button"
            onClick={() => setCreatingNew(true)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-dashed rounded-md hover:bg-gray-50 transition-colors text-sm text-gray-700"
            aria-label="Create new folder"
          >
            <Plus className="h-4 w-4" />
            <span>Create New Folder</span>
          </button>
        </div>
      )}
    </div>
  );
}
