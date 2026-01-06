import { useState, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listFilesForCompletion } from '@/api/directories';
import type { FileEntry } from '@/types/api';

export interface MentionState {
  isActive: boolean;
  query: string;
  startIndex: number;
  currentPath: string;
  isQuoted: boolean; // Whether the mention is in @"..." format
}

export interface UseMentionCompletionOptions {
  basePath: string;
  enabled?: boolean;
}

export interface UseMentionCompletionResult {
  mentionState: MentionState;
  completions: FileEntry[];
  isLoading: boolean;
  selectedIndex: number;
  handleInputChange: (value: string, cursorPosition: number) => void;
  handleKeyDown: (e: React.KeyboardEvent) => { handled: boolean; selectedEntry?: FileEntry };
  selectCompletion: (entry: FileEntry) => string;
  resetMention: () => void;
}

/**
 * Check if a path needs quoting (contains spaces or special characters).
 */
function needsQuoting(path: string): boolean {
  return !/^[a-zA-Z0-9_\-/.:]+$/.test(path);
}

/**
 * Format a path as an @mention, quoting if necessary.
 */
function formatMention(path: string, forceQuoted: boolean = false): string {
  if (forceQuoted || needsQuoting(path)) {
    return `@"${path}"`;
  }
  return `@${path}`;
}

/**
 * Hook for handling @mention file completion in text input.
 *
 * Detects when user types @ and provides file/directory completions
 * with keyboard navigation support.
 *
 * Supports two mention formats:
 * 1. Simple: @path/to/file.md (no spaces)
 * 2. Quoted: @"path with spaces/file.md" (spaces allowed)
 */
export function useMentionCompletion({
  basePath,
  enabled = true,
}: UseMentionCompletionOptions): UseMentionCompletionResult {
  const [mentionState, setMentionState] = useState<MentionState>({
    isActive: false,
    query: '',
    startIndex: 0,
    currentPath: '',
    isQuoted: false,
  });
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Parse the query to extract path and prefix for nested navigation
  const { searchPath, searchPrefix } = useMemo(() => {
    const query = mentionState.query;
    const lastSlash = query.lastIndexOf('/');

    if (lastSlash === -1) {
      // No slash - search in base path with query as prefix
      return { searchPath: basePath, searchPrefix: query };
    }

    // Has slash - navigate into subdirectory
    const pathPart = query.substring(0, lastSlash);
    const prefixPart = query.substring(lastSlash + 1);
    const fullPath = basePath ? `${basePath}/${pathPart}` : pathPart;

    return { searchPath: fullPath, searchPrefix: prefixPart };
  }, [basePath, mentionState.query]);

  // Fetch completions when mention is active
  const { data, isLoading } = useQuery({
    queryKey: ['fileCompletion', searchPath, searchPrefix],
    queryFn: () => listFilesForCompletion(searchPath, searchPrefix, 50),
    enabled: enabled && mentionState.isActive,
    staleTime: 5000, // Cache for 5 seconds
  });

  const completions = data?.entries ?? [];

  // Detect @mention in input (both simple and quoted formats)
  const handleInputChange = useCallback((value: string, cursorPosition: number) => {
    // First, try to find a quoted mention: @"..."
    // Look backwards from cursor for @" pattern
    let atIndex = -1;
    let isQuoted = false;
    const queryEndIndex = cursorPosition;

    // Search backwards for @ symbol
    for (let i = cursorPosition - 1; i >= 0; i--) {
      const char = value[i];

      // Check for quoted mention start: @"
      if (char === '"' && i > 0 && value[i - 1] === '@') {
        // Found @" - this is a quoted mention
        atIndex = i - 1;
        isQuoted = true;
        // Query is everything between @" and cursor (or closing quote)
        const closingQuote = value.indexOf('"', i + 1);
        if (closingQuote !== -1 && closingQuote < cursorPosition) {
          // Cursor is after the closing quote - not in a mention
          atIndex = -1;
          isQuoted = false;
        }
        break;
      }

      // Check for simple mention: @ followed by valid chars
      if (char === '@') {
        // Check if this is start of a quoted mention
        if (i + 1 < value.length && value[i + 1] === '"') {
          // This is @" - will be handled above on next iteration
          continue;
        }
        atIndex = i;
        isQuoted = false;
        break;
      }

      // For simple mentions, stop at whitespace
      if (!isQuoted && (char === ' ' || char === '\n' || char === '\t')) {
        break;
      }
    }

    if (atIndex === -1) {
      // No @ found before cursor
      if (mentionState.isActive) {
        setMentionState({ isActive: false, query: '', startIndex: 0, currentPath: '', isQuoted: false });
        setSelectedIndex(0);
      }
      return;
    }

    // Extract query after @ (or @")
    const queryStart = isQuoted ? atIndex + 2 : atIndex + 1;
    const query = value.substring(queryStart, queryEndIndex);

    // For simple mentions, validate characters
    if (!isQuoted && needsQuoting(query) && query.length > 0) {
      // Query contains characters that need quoting but we're not in quoted mode
      // This could happen if user manually types a space - deactivate
      if (query.includes(' ')) {
        setMentionState({ isActive: false, query: '', startIndex: 0, currentPath: '', isQuoted: false });
        setSelectedIndex(0);
        return;
      }
    }

    // Activate or update mention state
    setMentionState({
      isActive: true,
      query,
      startIndex: atIndex,
      currentPath: searchPath,
      isQuoted,
    });

    // Reset selection when query changes
    if (query !== mentionState.query) {
      setSelectedIndex(0);
    }
  }, [mentionState.isActive, mentionState.query, searchPath]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent): { handled: boolean; selectedEntry?: FileEntry } => {
    if (!mentionState.isActive || completions.length === 0) {
      return { handled: false };
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % completions.length);
        return { handled: true };

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + completions.length) % completions.length);
        return { handled: true };

      case 'Enter':
      case 'Tab': {
        e.preventDefault();
        const selected = completions[selectedIndex];
        return { handled: true, selectedEntry: selected };
      }

      case 'Escape':
        e.preventDefault();
        setMentionState({ isActive: false, query: '', startIndex: 0, currentPath: '', isQuoted: false });
        setSelectedIndex(0);
        return { handled: true };

      default:
        return { handled: false };
    }
  }, [mentionState.isActive, completions, selectedIndex]);

  // Generate the replacement text for a selected completion
  const selectCompletion = useCallback((entry: FileEntry): string => {
    // Build the full path from the query path + entry name
    const queryPath = mentionState.query;
    const lastSlash = queryPath.lastIndexOf('/');

    let fullPath: string;
    if (lastSlash === -1) {
      // No subdirectory navigation - just the entry name
      fullPath = entry.name;
    } else {
      // Preserve the path prefix and add entry name
      fullPath = queryPath.substring(0, lastSlash + 1) + entry.name;
    }

    // Add trailing slash for directories to enable continued navigation
    if (entry.is_directory) {
      fullPath += '/';
    }

    // Use quoted format if:
    // 1. Already in quoted mode, or
    // 2. The path needs quoting (contains spaces/special chars)
    return formatMention(fullPath, mentionState.isQuoted);
  }, [mentionState.query, mentionState.isQuoted]);

  const resetMention = useCallback(() => {
    setMentionState({ isActive: false, query: '', startIndex: 0, currentPath: '', isQuoted: false });
    setSelectedIndex(0);
  }, []);

  return {
    mentionState,
    completions,
    isLoading,
    selectedIndex,
    handleInputChange,
    handleKeyDown,
    selectCompletion,
    resetMention,
  };
}
