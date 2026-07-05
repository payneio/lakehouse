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
  getBundleSource,
  getResolvedBundle,
  updateBundle,
  type ResolvedBundle,
  type ResolvedModuleRef,
} from '@/api/bundles';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

type EditorMode = 'visual' | 'source';

interface BundleEditDialogProps {
  bundleName: string | null;
  open: boolean;
  onClose: () => void;
}

export function BundleEditDialog({ bundleName, open, onClose }: BundleEditDialogProps) {
  if (!open || !bundleName) return null;

  return <BundleEditDialogContent bundleName={bundleName} onClose={onClose} />;
}

// Inner component that only mounts when dialog is open
// This ensures state resets when dialog reopens
function BundleEditDialogContent({
  bundleName,
  onClose,
}: {
  bundleName: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<EditorMode>('source');
  const [editedContent, setEditedContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch source content
  const { data: source, isLoading: sourceLoading } = useQuery({
    queryKey: ['bundle', bundleName, 'source'],
    queryFn: () => getBundleSource(bundleName),
  });

  // Fetch resolved bundle for visual mode
  const { data: resolved, isLoading: resolvedLoading } = useQuery({
    queryKey: ['bundle', bundleName, 'resolved'],
    queryFn: () => getResolvedBundle(bundleName),
    enabled: mode === 'visual',
  });

  // Derive current content: edited content if user made changes, otherwise source
  const currentContent = editedContent ?? source?.content ?? '';
  const hasChanges = editedContent !== null && editedContent !== source?.content;

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (content: string) => updateBundle(bundleName, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bundles'] });
      queryClient.invalidateQueries({ queryKey: ['bundle', bundleName] });
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
              Edit Bundle: {bundleName}
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
            <VisualEditor bundle={resolved} />
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              Failed to load bundle structure
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
        Edit the raw bundle file (YAML frontmatter + Markdown body)
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
  bundle: ResolvedBundle;
}

function VisualEditor({ bundle }: VisualEditorProps) {
  // Visual editor provides a structured view but editing modifies the source
  // For now, this is a read-only view that helps understand the bundle structure
  // Full visual editing would require parsing/regenerating YAML which is complex

  return (
    <div className="h-full overflow-y-auto space-y-4 pr-2">
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <div className="text-sm text-amber-700">
          <strong>Visual Mode</strong>: View the resolved bundle structure. Switch to Source mode to edit the raw file.
        </div>
      </div>

      {/* Composition Chain */}
      {bundle.includesChain.length > 1 && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm font-medium text-blue-700 mb-2">
            Composition Chain
          </div>
          <div className="flex items-center gap-2 text-sm text-blue-600 flex-wrap">
            {bundle.includesChain.map((name, idx) => (
              <span key={name} className="flex items-center gap-2">
                <span className={idx === bundle.includesChain.length - 1 ? 'font-medium' : ''}>
                  {name}
                </span>
                {idx < bundle.includesChain.length - 1 && (
                  <ChevronRight className="h-4 w-4 text-blue-400" />
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Session Config */}
      {bundle.session && (bundle.session.orchestrator || bundle.session.context) && (
        <EditableModuleSection
          icon={<Settings className="h-4 w-4" />}
          title="Session Configuration"
          defaultExpanded
        >
          {bundle.session.orchestrator && (
            <EditableModuleItem
              module={{
                module: bundle.session.orchestrator.module,
                source: bundle.session.orchestrator.source,
                config: bundle.session.orchestrator.config,
                definedIn: bundle.session.orchestrator.definedIn,
                overridden: bundle.session.orchestrator.overridden,
              }}
              label="Orchestrator"
              bundleName={bundle.name}
            />
          )}
          {bundle.session.context && (
            <EditableModuleItem
              module={{
                module: bundle.session.context.module,
                source: bundle.session.context.source,
                config: bundle.session.context.config,
                definedIn: bundle.session.context.definedIn,
                overridden: bundle.session.context.overridden,
              }}
              label="Context Manager"
              bundleName={bundle.name}
            />
          )}
        </EditableModuleSection>
      )}

      {/* Providers */}
      {bundle.providers.length > 0 && (
        <EditableModuleSection
          icon={<Server className="h-4 w-4" />}
          title={`Providers (${bundle.providers.length})`}
        >
          {bundle.providers.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} bundleName={bundle.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Tools */}
      {bundle.tools.length > 0 && (
        <EditableModuleSection
          icon={<Wrench className="h-4 w-4" />}
          title={`Tools (${bundle.tools.length})`}
        >
          {bundle.tools.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} bundleName={bundle.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Hooks */}
      {bundle.hooks.length > 0 && (
        <EditableModuleSection
          icon={<Zap className="h-4 w-4" />}
          title={`Hooks (${bundle.hooks.length})`}
        >
          {bundle.hooks.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} bundleName={bundle.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* Agents */}
      {bundle.agents.length > 0 && (
        <EditableModuleSection
          icon={<Bot className="h-4 w-4" />}
          title={`Agents (${bundle.agents.length})`}
        >
          {bundle.agents.map((mod) => (
            <EditableModuleItem key={mod.module} module={mod} bundleName={bundle.name} />
          ))}
        </EditableModuleSection>
      )}

      {/* System Instruction */}
      {bundle.instruction && (
        <EditableModuleSection
          icon={<FileText className="h-4 w-4" />}
          title="System Instruction"
        >
          <pre className="text-xs bg-muted text-foreground p-3 rounded overflow-x-auto whitespace-pre-wrap">
            {bundle.instruction}
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
  bundleName: string;
}

function EditableModuleItem({ module, label, bundleName }: EditableModuleItemProps) {
  const [showConfig, setShowConfig] = useState(false);
  const hasConfig = module.config && Object.keys(module.config).length > 0;

  // Determine styling based on source
  const isLocal = module.definedIn === bundleName;
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
