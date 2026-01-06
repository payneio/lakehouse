import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Highlight, themes, type Language } from 'prism-react-renderer';
import { ChevronLeft, ChevronRight, Download, Eye, File, Folder, FolderOpen, X } from 'lucide-react';
import { listFilesForCompletion, getFileContent, getFileDownloadUrl } from '@/api/directories';
import type { FileEntry, FileContentResponse } from '@/types/api';

interface FileBrowserPanelProps {
  basePath: string;
  isOpen: boolean;
  onClose: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getLanguageFromMimeType(mimeType: string, fileName: string): string {
  // Check extension first for better accuracy
  const ext = fileName.split('.').pop()?.toLowerCase();
  const extMap: Record<string, string> = {
    'ts': 'typescript',
    'tsx': 'typescript',
    'js': 'javascript',
    'jsx': 'javascript',
    'py': 'python',
    'md': 'markdown',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'sql': 'sql',
    'sh': 'bash',
    'bash': 'bash',
    'rs': 'rust',
    'go': 'go',
    'java': 'java',
    'rb': 'ruby',
    'php': 'php',
    'xml': 'xml',
    'toml': 'toml',
  };
  if (ext && extMap[ext]) return extMap[ext];

  // Fallback to mime type
  if (mimeType.includes('javascript')) return 'javascript';
  if (mimeType.includes('typescript')) return 'typescript';
  if (mimeType.includes('python')) return 'python';
  if (mimeType.includes('json')) return 'json';
  if (mimeType.includes('html')) return 'html';
  if (mimeType.includes('css')) return 'css';
  return 'plaintext';
}

export function FileBrowserPanel({ basePath, isOpen, onClose }: FileBrowserPanelProps) {
  const [currentPath, setCurrentPath] = useState(basePath);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // Fetch directory contents
  const { data: filesData, isLoading: isLoadingFiles } = useQuery({
    queryKey: ['fileBrowser', currentPath],
    queryFn: () => listFilesForCompletion(currentPath, '', 200),
    enabled: isOpen,
  });

  // Fetch file content when a file is selected
  const { data: fileContent, isLoading: isLoadingContent } = useQuery({
    queryKey: ['fileContent', selectedFile],
    queryFn: () => getFileContent(selectedFile!),
    enabled: !!selectedFile,
  });

  const entries = filesData?.entries ?? [];

  const handleEntryClick = useCallback((entry: FileEntry) => {
    if (entry.is_directory) {
      // Navigate into directory
      const newPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      setCurrentPath(newPath);
      setSelectedFile(null);
    } else {
      // Select file for viewing
      const filePath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      setSelectedFile(filePath);
    }
  }, [currentPath]);

  const handleGoUp = useCallback(() => {
    if (!currentPath || currentPath === basePath) return;
    const parts = currentPath.split('/');
    parts.pop();
    const newPath = parts.join('/');
    // Don't go above basePath
    if (newPath.length < basePath.length) {
      setCurrentPath(basePath);
    } else {
      setCurrentPath(newPath);
    }
    setSelectedFile(null);
  }, [currentPath, basePath]);

  const handleBackToList = useCallback(() => {
    setSelectedFile(null);
  }, []);

  // Calculate display path (relative to basePath)
  const displayPath = currentPath.startsWith(basePath)
    ? currentPath.slice(basePath.length).replace(/^\//, '') || '/'
    : currentPath;

  const canGoUp = currentPath !== basePath && currentPath.length > basePath.length;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[500px] md:w-[600px] bg-background border-l shadow-lg z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2 min-w-0">
          <FolderOpen className="h-5 w-5 flex-shrink-0 text-muted-foreground" />
          <span className="font-medium truncate">
            {selectedFile ? 'File Viewer' : 'File Browser'}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-accent rounded-md"
          title="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Breadcrumb / Path */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/50 text-sm">
        {selectedFile ? (
          <>
            <button
              onClick={handleBackToList}
              className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to list
            </button>
            <span className="text-muted-foreground">/</span>
            <span className="truncate font-mono text-xs">{selectedFile.split('/').pop()}</span>
          </>
        ) : (
          <>
            {canGoUp && (
              <button
                onClick={handleGoUp}
                className="p-1 hover:bg-accent rounded-md"
                title="Go up"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
            <span className="font-mono text-xs truncate">{displayPath}</span>
          </>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {selectedFile ? (
          // File viewer
          <FileViewer
            filePath={selectedFile}
            content={fileContent}
            isLoading={isLoadingContent}
          />
        ) : (
          // File list
          <FileList
            entries={entries}
            isLoading={isLoadingFiles}
            currentPath={currentPath}
            onEntryClick={handleEntryClick}
          />
        )}
      </div>
    </div>
  );
}

interface FileListProps {
  entries: FileEntry[];
  isLoading: boolean;
  currentPath: string;
  onEntryClick: (entry: FileEntry) => void;
}

function FileList({ entries, isLoading, currentPath, onEntryClick }: FileListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-muted-foreground">
        Empty directory
      </div>
    );
  }

  return (
    <div className="divide-y">
      {entries.map((entry) => {
        const fullPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
        const downloadUrl = getFileDownloadUrl(fullPath);

        return (
          <div
            key={entry.path}
            className="flex items-center gap-3 px-4 py-2 hover:bg-accent/50 group"
          >
            <button
              onClick={() => onEntryClick(entry)}
              className="flex items-center gap-3 flex-1 min-w-0 text-left"
            >
              {entry.is_directory ? (
                <Folder className="h-4 w-4 flex-shrink-0 text-blue-500" />
              ) : (
                <File className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
              )}
              <span className="truncate">{entry.name}</span>
              {entry.is_directory && (
                <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground ml-auto" />
              )}
            </button>
            {!entry.is_directory && (
              <a
                href={downloadUrl}
                download
                className="p-1.5 hover:bg-accent rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                title="Download"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="h-4 w-4 text-muted-foreground" />
              </a>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface FileViewerProps {
  filePath: string;
  content: FileContentResponse | undefined;
  isLoading: boolean;
}

function FileViewer({ filePath, content, isLoading }: FileViewerProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8 text-muted-foreground">
        Loading file...
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex items-center justify-center p-8 text-muted-foreground">
        Failed to load file
      </div>
    );
  }

  const downloadUrl = getFileDownloadUrl(filePath);

  if (!content.is_viewable) {
    return (
      <div className="flex flex-col items-center justify-center p-8 gap-4">
        <File className="h-16 w-16 text-muted-foreground" />
        <div className="text-center">
          <p className="font-medium">{content.name}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {formatFileSize(content.size)} &middot; {content.mime_type}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            This file cannot be previewed
          </p>
        </div>
        <a
          href={downloadUrl}
          download
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          <Download className="h-4 w-4" />
          Download
        </a>
      </div>
    );
  }

  // Image viewer
  if (content.is_image) {
    return (
      <div className="flex flex-col h-full">
        {/* File info bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 text-sm">
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">
              {formatFileSize(content.size)}
            </span>
          </div>
          <a
            href={downloadUrl}
            download
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <Download className="h-4 w-4" />
            Download
          </a>
        </div>

        {/* Image content */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-4 bg-muted/20">
          <img
            src={downloadUrl}
            alt={content.name}
            className="max-w-full max-h-full object-contain"
          />
        </div>
      </div>
    );
  }

  // Text viewer
  const language = getLanguageFromMimeType(content.mime_type, content.name);

  return (
    <div className="flex flex-col h-full">
      {/* File info bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 text-sm">
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">
            {formatFileSize(content.size)}
          </span>
        </div>
        <a
          href={downloadUrl}
          download
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <Download className="h-4 w-4" />
          Download
        </a>
      </div>

      {/* File content with syntax highlighting */}
      <div className="flex-1 overflow-auto">
        <Highlight theme={themes.vsLight} code={content.content} language={language as Language}>
          {({ style, tokens, getLineProps, getTokenProps }) => (
            <pre style={style} className="p-4 text-sm font-mono whitespace-pre-wrap break-words m-0">
              {tokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })}>
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </pre>
          )}
        </Highlight>
      </div>
    </div>
  );
}
