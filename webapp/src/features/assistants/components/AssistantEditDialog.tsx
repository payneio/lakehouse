import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronRight,
  Save,
  X,
  AlertCircle,
  Settings,
  Server,
  Wrench,
  Zap,
  Bot,
  FileText,
  RotateCcw,
  Edit2,
} from 'lucide-react';
import { useState } from 'react';
import {
  getAssistantSource,
  getResolvedAssistant,
  updateAssistant,
  type ResolvedAssistant,
  type ResolvedModuleRef,
} from '@/api/assistants';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

type EditorMode = 'visual' | 'source';

interface AssistantEditDialogProps {
  assistantName: string | null;
  open: boolean;
  onClose: () => void;
}

export function AssistantEditDialog({ assistantName, open, onClose }: AssistantEditDialogProps) {
  if (!open || !assistantName) return null;

  return <AssistantEditDialogContent assistantName={assistantName} onClose={onClose} />;
}

// Inner component that only mounts when dialog is open
// This ensures state resets when dialog reopens
function AssistantEditDialogContent({
  assistantName,
  onClose,
}: {
  assistantName: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<EditorMode>('source');
  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch source content
  const { data: source, isLoading: sourceLoading } = useQuery({
    queryKey: ['assistant', assistantName, 'source'],
    queryFn: () => getAssistantSource(assistantName),
  });

  // Fetch resolved assistant for visual mode
  const { data: resolved, isLoading: resolvedLoading } = useQuery({
    queryKey: ['assistant', assistantName, 'resolved'],
    queryFn: () => getResolvedAssistant(assistantName),
    enabled: mode === 'visual',
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
      onClose();
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

  const handleSourceChange = (value: string) => {
    setEditedContent(value);
  };

  const handleReset = () => {
    setEditedContent(null);
  };

  const isLoading = sourceLoading || (mode === 'visual' && resolvedLoading);

  return (
    <Dialog open onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2">
              <Edit2 className="h-5 w-5" />
              Edit Assistant: {assistantName}
            </DialogTitle>
            <div className="flex border rounded-md overflow-hidden">
              <button
                onClick={() => setMode('visual')}
                className={`px-3 py-1.5 text-sm ${
                  mode === 'visual'
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-accent'
                }`}
              >
                Visual
              </button>
              <button
                onClick={() => setMode('source')}
                className={`px-3 py-1.5 text-sm ${
                  mode === 'source'
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-accent'
                }`}
              >
                Source
              </button>
            </div>
          </div>
          {source && (
            <p className="text-xs text-muted-foreground">
              {source.path} ({source.format})
            </p>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-hidden">
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">Loading...</div>
          ) : mode === 'source' ? (
            <SourceEditor
              content={currentContent}
              onChange={handleSourceChange}
            />
          ) : resolved ? (
            <VisualEditor assistant={resolved} />
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              Failed to load assistant structure
            </div>
          )}
        </div>

        {error && (
          <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm">
            <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
            <div className="text-destructive">{error}</div>
          </div>
        )}

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
              onClick={handleClose}
              className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-md hover:bg-accent"
              disabled={saveMutation.isPending}
            >
              <X className="h-4 w-4" />
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              disabled={!hasChanges || saveMutation.isPending}
            >
              <Save className="h-4 w-4" />
              {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface SourceEditorProps {
  content: string;
  onChange: (value: string) => void;
}

function SourceEditor({ content, onChange }: SourceEditorProps) {
  return (
    <div className="h-full flex flex-col">
      <div className="text-xs text-muted-foreground mb-2 px-1">
        Edit the raw assistant file (YAML frontmatter + Markdown body)
      </div>
      <textarea
        value={content}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 w-full min-h-[400px] p-4 font-mono text-sm bg-muted text-foreground border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-primary"
        spellCheck={false}
      />
    </div>
  );
}

interface VisualEditorProps {
  assistant: ResolvedAssistant;
}

function VisualEditor({ assistant }: VisualEditorProps) {
  // Visual editor provides a structured view but editing modifies the source
  // For now, this is a read-only view that helps understand the assistant structure
  // Full visual editing would require parsing/regenerating YAML which is complex

  return (
    <div className="h-full overflow-y-auto space-y-4 pr-2">
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <div className="text-sm text-amber-700">
          <strong>Visual Mode</strong>: View the resolved assistant structure. Switch to Source mode to edit the raw file.
        </div>
      </div>

      {/* Composition Chain */}
      {assistant.includesChain.length > 1 && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm font-medium text-blue-700 mb-2">
            Composition Chain
          </div>
          <div className="flex items-center gap-2 text-sm text-blue-600 flex-wrap">
            {assistant.includesChain.map((name, idx) => (
              <span key={name} className="flex items-center gap-2">
                <span className={idx === assistant.includesChain.length - 1 ? 'font-medium' : ''}>
                  {name}
                </span>
                {idx < assistant.includesChain.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-blue-400" />
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Session Config */}
      {assistant.session && (assistant.session.orchestrator || assistant.session.context) && (
        <EditableModuleSection
          icon={<Settings className="h-4 w-4" />}
          title="Session Configuration"
          defaultExpanded
        >
          {assistant.session.orchestrator && (
            <EditableModuleItem
              module={{
                module: assistant.session.orchestrator.module,
                source: assistant.session.orchestrator.source,
                config: assistant.session.orchestrator.config,
                definedIn: assistant.session.orchestrator.definedIn,
                overridden: assistant.session.orchestrator.overridden,
              }}
              label="Orchestrator"
              assistantName={assistant.name}
            />
          )}
          {assistant.session.context && (
            <EditableModuleItem
              module={{
                module: assistant.session.context.module,
                source: assistant.session.context.source,
                config: assistant.session.context.config,
                definedIn: assistant.session.context.definedIn,
                overridden: assistant.session.context.overridden,
              }}
              label="Context Manager"
              assistantName={assistant.name}
            />
          )}
        </EditableModuleSection>
      )}

      {/* Providers */}
      {assistant.providers.length > 0 && (
        <EditableModuleSection
          icon={<Server className="h-4 w-4" />}
          title={`Providers (${assistant.providers.length})`}
        >
          {assistant.providers.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} assistantName={assistant.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Tools */}
      {assistant.tools.length > 0 && (
        <EditableModuleSection
          icon={<Wrench className="h-4 w-4" />}
          title={`Tools (${assistant.tools.length})`}
        >
          {assistant.tools.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} assistantName={assistant.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Hooks */}
      {assistant.hooks.length > 0 && (
        <EditableModuleSection
          icon={<Zap className="h-4 w-4" />}
          title={`Hooks (${assistant.hooks.length})`}
        >
          {assistant.hooks.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} assistantName={assistant.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Agents */}
      {assistant.agents.length > 0 && (
        <EditableModuleSection
          icon={<Bot className="h-4 w-4" />}
          title={`Agents (${assistant.agents.length})`}
        >
          {assistant.agents.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} assistantName={assistant.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* System Instruction */}
      {assistant.instruction && (
        <EditableModuleSection
          icon={<FileText className="h-4 w-4" />}
          title="System Instruction"
        >
          <pre className="text-xs bg-muted text-foreground p-3 rounded overflow-x-auto whitespace-pre-wrap">
            {assistant.instruction}
          </pre>
        </EditableModuleSection>
      )}
    </div>
  );
}

interface EditableModuleSectionProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  defaultExpanded?: boolean;
}

function EditableModuleSection({
  icon,
  title,
  children,
  defaultExpanded = false,
}: EditableModuleSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-accent/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          {icon}
          <span className="font-medium">{title}</span>
        </div>
      </button>
      {expanded && <div className="p-3 pt-0 space-y-2">{children}</div>}
    </div>
  );
}

interface EditableModuleItemProps {
  module: ResolvedModuleRef;
  label?: string;
  assistantName: string;
}

function EditableModuleItem({ module, label, assistantName }: EditableModuleItemProps) {
  const [showConfig, setShowConfig] = useState(false);
  const hasConfig = module.config && Object.keys(module.config).length > 0;

  // Determine styling based on source
  const isLocal = module.definedIn === assistantName;
  const isOverridden = module.overridden;

  let borderClass = 'border-border';
  let bgClass = 'bg-muted/50';
  let badgeClass = 'text-muted-foreground bg-muted';

  if (isLocal) {
    borderClass = 'border-green-200';
    bgClass = 'bg-green-50/50';
    badgeClass = 'text-green-600 bg-green-100';
  } else if (isOverridden) {
    borderClass = 'border-blue-200';
    bgClass = 'bg-blue-50/50';
    badgeClass = 'text-blue-600 bg-blue-100';
  }

  return (
    <div className={`border rounded p-2 ${borderClass} ${bgClass}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {label && <span className="text-xs text-muted-foreground">{label}:</span>}
          <span className="font-mono text-sm">{module.module}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${badgeClass}`}>
            {isLocal ? 'local' : isOverridden ? `overridden` : `from: ${module.definedIn}`}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {hasConfig && (
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="text-xs text-blue-600 hover:underline"
            >
              {showConfig ? 'Hide' : 'Config'}
            </button>
          )}
        </div>
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
      {isOverridden && module.originalConfig && (
        <div className="text-xs mt-1 text-muted-foreground">
          Original: {JSON.stringify(module.originalConfig)}
        </div>
      )}
    </div>
  );
}
