import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronRight,
  Package,
  Server,
  Wrench,
  Zap,
  Bot,
  Settings,
  FileText,
  Copy,
  Save,
  RotateCcw,
  AlertCircle,
  Trash2,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import { useState } from 'react';
import {
  getResolvedAssistant,
  getAssistantSource,
  updateAssistant,
  renameAssistant,
  type ResolvedAssistant,
  type ResolvedModuleRef,
  type IncludesTreeNode,
} from '@/api/assistants';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

type ViewMode = 'details' | 'source';

interface AssistantDetailDialogProps {
  assistantName: string | null;
  open: boolean;
  onClose: () => void;
  onCopy: () => void;
  onDelete?: () => void;
  onRename?: (newName: string) => void;
}

export function AssistantDetailDialog({
  assistantName,
  open,
  onClose,
  onCopy,
  onDelete,
  onRename,
}: AssistantDetailDialogProps) {
  if (!open || !assistantName) return null;

  return (
    <AssistantDetailDialogContent
      assistantName={assistantName}
      onClose={onClose}
      onCopy={onCopy}
      onDelete={onDelete}
      onRename={onRename}
    />
  );
}

// Inner component that only mounts when dialog is open
// This ensures state resets when dialog reopens
function AssistantDetailDialogContent({
  assistantName,
  onClose,
  onCopy,
  onDelete,
  onRename,
}: {
  assistantName: string;
  onClose: () => void;
  onCopy: () => void;
  onDelete?: () => void;
  onRename?: (newName: string) => void;
}) {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>('details');
  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [newName, setNewName] = useState(assistantName);

  const isEditable = true;

  const { data: assistant, isLoading: assistantLoading, error: assistantError } = useQuery({
    queryKey: ['assistant', assistantName, 'resolved'],
    queryFn: () => getResolvedAssistant(assistantName),
  });

  const { data: source, isLoading: sourceLoading, error: sourceError } = useQuery({
    queryKey: ['assistant', assistantName, 'source'],
    queryFn: () => getAssistantSource(assistantName),
    enabled: viewMode === 'source',
  });

  // Derive current content: edited content if user made changes, otherwise source
  const currentContent = editedContent ?? source?.content ?? '';
  const hasChanges = editedContent !== null && editedContent !== source?.content;

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (content: string) => updateAssistant(assistantName, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assistants'] });
      queryClient.invalidateQueries({ queryKey: ['assistant', assistantName] });
      setEditedContent(null);
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  // Rename mutation
  const renameMutation = useMutation({
    mutationFn: (name: string) => renameAssistant(assistantName, name),
    onSuccess: (_, newAssistantName) => {
      queryClient.invalidateQueries({ queryKey: ['assistants'] });
      setIsEditingName(false);
      setError(null);
      onRename?.(newAssistantName);
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const handleClose = () => {
    if (hasChanges) {
      if (!confirm('You have unsaved changes. Are you sure you want to close?')) {
        return;
      }
    }
    setError(null);
    setEditedContent(null);
    onClose();
  };

  const handleSave = () => {
    setError(null);
    saveMutation.mutate(currentContent);
  };

  const handleReset = () => {
    setEditedContent(null);
  };

  const handleStartRename = () => {
    setNewName(assistantName);
    setIsEditingName(true);
  };

  const handleCancelRename = () => {
    setNewName(assistantName);
    setIsEditingName(false);
  };

  const handleConfirmRename = () => {
    if (newName && newName !== assistantName) {
      setError(null);
      renameMutation.mutate(newName);
    } else {
      setIsEditingName(false);
    }
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirmRename();
    } else if (e.key === 'Escape') {
      handleCancelRename();
    }
  };

  const isLoading = viewMode === 'details' ? assistantLoading : sourceLoading;
  const loadError = viewMode === 'details' ? assistantError : sourceError;

  return (
    <Dialog open onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Package className="h-6 w-6" />
              <div>
                {isEditingName ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      onKeyDown={handleRenameKeyDown}
                      className="px-2 py-1 text-lg font-semibold border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                      autoFocus
                      disabled={renameMutation.isPending}
                    />
                    <button
                      onClick={handleConfirmRename}
                      className="p-1 text-green-600 hover:bg-green-50 rounded"
                      disabled={renameMutation.isPending}
                      title="Confirm rename"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                    <button
                      onClick={handleCancelRename}
                      className="p-1 text-gray-500 hover:bg-gray-100 rounded"
                      disabled={renameMutation.isPending}
                      title="Cancel"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <DialogTitle>{assistantName}</DialogTitle>
                    {isEditable && (
                      <button
                        onClick={handleStartRename}
                        className="p-1 text-muted-foreground hover:text-foreground hover:bg-accent rounded"
                        title="Rename assistant"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                )}
                {assistant?.gitUrl && (
                  <div className="text-xs text-muted-foreground mt-1 font-mono truncate max-w-md" title={assistant.gitUrl}>
                    {assistant.gitUrl}
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* View toggle */}
              <div className="flex border rounded-md overflow-hidden">
                <button
                  onClick={() => setViewMode('details')}
                  className={`px-3 py-1.5 text-sm ${
                    viewMode === 'details'
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                  }`}
                >
                  Details
                </button>
                <button
                  onClick={() => setViewMode('source')}
                  className={`px-3 py-1.5 text-sm ${
                    viewMode === 'source'
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                  }`}
                >
                  Source
                </button>
              </div>
              <button
                onClick={onCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent"
              >
                <Copy className="h-4 w-4" />
                Copy
              </button>
              {onDelete && (
                <button
                  onClick={onDelete}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-md hover:bg-red-50"
                  title="Delete assistant"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </button>
              )}
            </div>
          </div>
          {viewMode === 'source' && source && (
            <p className="text-xs text-muted-foreground mt-1">
              {source.path} ({source.format})
              {isEditable && <span className="ml-2 text-green-600">• Editable</span>}
            </p>
          )}
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">Loading...</div>
          ) : loadError ? (
            <div className="py-8 text-center text-red-500">Failed to load assistant</div>
          ) : viewMode === 'details' && assistant ? (
            <AssistantDetailContent assistant={assistant} />
          ) : viewMode === 'source' && source ? (
            isEditable ? (
              <div className="h-full flex flex-col">
                <textarea
                  value={currentContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  className="flex-1 w-full min-h-[400px] p-4 font-mono text-sm bg-muted text-foreground border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                  spellCheck={false}
                />
              </div>
            ) : (
              <pre className="text-sm bg-muted text-foreground p-4 rounded overflow-auto font-mono whitespace-pre h-full">
                {source.content}
              </pre>
            )
          ) : null}
        </div>

        {error && (
          <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
            <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
            <div className="text-destructive">{error}</div>
          </div>
        )}

        {/* Footer with save controls for editable assistants in source mode */}
        {viewMode === 'source' && isEditable && (
          <DialogFooter className="flex items-center justify-between border-t pt-4">
            <div className="flex items-center gap-2">
              {hasChanges && (
                <span className="text-sm text-amber-600">Unsaved changes</span>
              )}
            </div>
            <div className="flex gap-2">
              {hasChanges && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-md hover:bg-accent"
                  disabled={saveMutation.isPending}
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset
                </button>
              )}
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                disabled={!hasChanges || saveMutation.isPending}
              >
                <Save className="h-4 w-4" />
                {saveMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AssistantDetailContent({ assistant }: { assistant: ResolvedAssistant }) {
  return (
    <div className="space-y-4 mt-4">
      {/* Composition Tree */}
      {assistant.includesTree && assistant.includesTree.includes.length > 0 && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm font-medium text-blue-700 mb-2">
            Composition Tree
          </div>
          <div className="text-sm text-blue-600 font-mono">
            <IncludesTree node={assistant.includesTree} isRoot />
          </div>
        </div>
      )}

      {/* Session Config */}
      {assistant.session && (assistant.session.orchestrator || assistant.session.context) && (
        <ModuleSection
          icon={<Settings className="h-4 w-4" />}
          title="Session Configuration"
          defaultExpanded
        >
          {assistant.session.orchestrator && (
            <ModuleItem
              module={{
                module: assistant.session.orchestrator.module,
                source: assistant.session.orchestrator.source,
                config: assistant.session.orchestrator.config,
                definedIn: assistant.session.orchestrator.definedIn,
                overridden: assistant.session.orchestrator.overridden,
              }}
              label="Orchestrator"
            />
          )}
          {assistant.session.context && (
            <ModuleItem
              module={{
                module: assistant.session.context.module,
                source: assistant.session.context.source,
                config: assistant.session.context.config,
                definedIn: assistant.session.context.definedIn,
                overridden: assistant.session.context.overridden,
              }}
              label="Context Manager"
            />
          )}
        </ModuleSection>
      )}

      {/* Providers */}
      {assistant.providers.length > 0 && (
        <ModuleSection
          icon={<Server className="h-4 w-4" />}
          title={`Providers (${assistant.providers.length})`}
        >
          {assistant.providers.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Tools */}
      {assistant.tools.length > 0 && (
        <ModuleSection
          icon={<Wrench className="h-4 w-4" />}
          title={`Tools (${assistant.tools.length})`}
        >
          {assistant.tools.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Hooks */}
      {assistant.hooks.length > 0 && (
        <ModuleSection
          icon={<Zap className="h-4 w-4" />}
          title={`Hooks (${assistant.hooks.length})`}
        >
          {assistant.hooks.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Agents */}
      {assistant.agents.length > 0 && (
        <ModuleSection
          icon={<Bot className="h-4 w-4" />}
          title={`Agents (${assistant.agents.length})`}
        >
          {assistant.agents.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* System Instruction */}
      {assistant.instruction && (
        <ModuleSection
          icon={<FileText className="h-4 w-4" />}
          title="System Instruction"
        >
          <pre className="text-xs bg-muted text-foreground p-3 rounded overflow-x-auto whitespace-pre-wrap">
            {assistant.instruction}
          </pre>
        </ModuleSection>
      )}
    </div>
  );
}

interface ModuleSectionProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

function ModuleSection({ icon, title, children, defaultExpanded = false }: ModuleSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-3 hover:bg-accent/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        {icon}
        <span className="font-medium">{title}</span>
      </button>
      {expanded && <div className="p-3 pt-0 space-y-2">{children}</div>}
    </div>
  );
}

interface ModuleItemProps {
  module: ResolvedModuleRef;
  label?: string;
}

function ModuleItem({ module, label }: ModuleItemProps) {
  const [showConfig, setShowConfig] = useState(false);
  const hasConfig = module.config && Object.keys(module.config).length > 0;

  // Determine color based on source
  const sourceColor = module.overridden
    ? 'text-blue-600 bg-blue-50'
    : 'text-muted-foreground bg-muted';

  return (
    <div className="border rounded p-2 bg-muted/50">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {label && <span className="text-xs text-muted-foreground">{label}:</span>}
          <span className="font-mono text-sm">{module.module}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${sourceColor}`}>
            {module.overridden ? `overridden in ${module.overrideIn}` : `from: ${module.definedIn}`}
          </span>
        </div>
        {hasConfig && (
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showConfig ? 'Hide Config' : 'Show Config'}
          </button>
        )}
      </div>
      {module.source && (
        <div className="text-xs text-muted-foreground mt-1 truncate" title={module.source}>
          {module.source}
        </div>
      )}
      {showConfig && hasConfig && (
        <pre className="text-xs mt-2 p-2 bg-muted text-foreground rounded overflow-x-auto">
          {JSON.stringify(module.config, null, 2)}
        </pre>
      )}
      {module.overridden && module.originalConfig && (
        <div className="text-xs mt-1 text-muted-foreground">
          Original config: {JSON.stringify(module.originalConfig)}
        </div>
      )}
    </div>
  );
}

interface IncludesTreeProps {
  node: IncludesTreeNode;
  isRoot?: boolean;
  isLast?: boolean;
  prefix?: string;
}

function IncludesTree({ node, isRoot = false, isLast = false, prefix = '' }: IncludesTreeProps) {
  const connector = isRoot ? '' : (isLast ? '└─ ' : '├─ ');
  const childPrefix = isRoot ? '' : prefix + (isLast ? '   ' : '│  ');

  return (
    <div>
      <div className={isRoot ? 'font-semibold' : ''}>
        <span className="text-blue-400">{prefix}{connector}</span>
        {node.name}
      </div>
      {node.includes.map((child, idx) => (
        <IncludesTree
          key={child.name}
          node={child}
          isLast={idx === node.includes.length - 1}
          prefix={childPrefix}
        />
      ))}
    </div>
  );
}
