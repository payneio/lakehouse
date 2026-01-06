import { Folder, File } from 'lucide-react';
import type { FileEntry } from '@/types/api';

interface FileCompletionDropdownProps {
  entries: FileEntry[];
  selectedIndex: number;
  isLoading: boolean;
  onSelect: (entry: FileEntry) => void;
}

/**
 * Dropdown component for displaying file/directory completion options.
 * Renders above the input field with keyboard navigation support.
 */
export function FileCompletionDropdown({
  entries,
  selectedIndex,
  isLoading,
  onSelect,
}: FileCompletionDropdownProps) {
  if (entries.length === 0 && !isLoading) {
    return (
      <div className="absolute bottom-full left-0 right-0 mb-1 bg-popover border rounded-md shadow-lg p-2 text-sm text-muted-foreground">
        No matches found
      </div>
    );
  }

  return (
    <div className="absolute bottom-full left-0 right-0 mb-1 bg-popover border rounded-md shadow-lg max-h-64 overflow-y-auto">
      {isLoading && entries.length === 0 ? (
        <div className="p-2 text-sm text-muted-foreground">Loading...</div>
      ) : (
        <ul className="py-1">
          {entries.map((entry, index) => (
            <li key={entry.path}>
              <button
                type="button"
                className={`w-full px-3 py-1.5 flex items-center gap-2 text-sm text-left hover:bg-accent ${
                  index === selectedIndex ? 'bg-accent' : ''
                }`}
                onClick={() => onSelect(entry)}
                onMouseDown={(e) => e.preventDefault()} // Prevent blur
              >
                {entry.is_directory ? (
                  <Folder className="h-4 w-4 text-blue-500 flex-shrink-0" />
                ) : (
                  <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                )}
                <span className="truncate">{entry.name}</span>
                {entry.is_directory && (
                  <span className="text-muted-foreground text-xs ml-auto">/</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
