import { useQuery } from '@tanstack/react-query';
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
} from 'lucide-react';
import { useState } from 'react';
import { getResolvedBundle, getBundleSource, type ResolvedBundle, type ResolvedModuleRef } from '@/api/bundles';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

type ViewMode = 'details' | 'source';

interface BundleDetailDialogProps {
  bundleName: string | null;
  bundleSource: 'user' | 'system' | null;
  open: boolean;
  onClose: () => void;
  onCopy: () => void;
}

export function BundleDetailDialog({
  bundleName,
  bundleSource,
  open,
  onClose,
  onCopy,
}: BundleDetailDialogProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('details');

  const { data: bundle, isLoading: bundleLoading, error: bundleError } = useQuery({
    queryKey: ['bundle', bundleName, 'resolved'],
    queryFn: () => getResolvedBundle(bundleName!),
    enabled: !!bundleName && open,
  });

  const { data: source, isLoading: sourceLoading, error: sourceError } = useQuery({
    queryKey: ['bundle', bundleName, 'source'],
    queryFn: () => getBundleSource(bundleName!),
    enabled: !!bundleName && open && viewMode === 'source',
  });

  // Reset view mode when dialog closes
  const handleClose = () => {
    setViewMode('details');
    onClose();
  };

  if (!bundleName) return null;

  const isLoading = viewMode === 'details' ? bundleLoading : sourceLoading;
  const error = viewMode === 'details' ? bundleError : sourceError;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Package className="h-6 w-6" />
              <div>
                <DialogTitle>{bundleName}</DialogTitle>
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    bundleSource === 'user'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {bundleSource === 'user' ? 'User' : 'System'}
                </span>
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
            </div>
          </div>
          {viewMode === 'source' && source && (
            <p className="text-xs text-muted-foreground mt-1">
              {source.path} ({source.format})
            </p>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">Loading...</div>
          ) : error ? (
            <div className="py-8 text-center text-red-500">Failed to load bundle</div>
          ) : viewMode === 'details' && bundle ? (
            <BundleDetailContent bundle={bundle} />
          ) : viewMode === 'source' && source ? (
            <pre className="text-sm bg-muted text-foreground p-4 rounded overflow-x-auto font-mono whitespace-pre">
              {source.content}
            </pre>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function BundleDetailContent({ bundle }: { bundle: ResolvedBundle }) {
  return (
    <div className="space-y-4 mt-4">
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
        <ModuleSection
          icon={<Settings className="h-4 w-4" />}
          title="Session Configuration"
          defaultExpanded
        >
          {bundle.session.orchestrator && (
            <ModuleItem
              module={{
                module: bundle.session.orchestrator.module,
                source: bundle.session.orchestrator.source,
                config: bundle.session.orchestrator.config,
                definedIn: bundle.session.orchestrator.definedIn,
                overridden: bundle.session.orchestrator.overridden,
              }}
              label="Orchestrator"
            />
          )}
          {bundle.session.context && (
            <ModuleItem
              module={{
                module: bundle.session.context.module,
                source: bundle.session.context.source,
                config: bundle.session.context.config,
                definedIn: bundle.session.context.definedIn,
                overridden: bundle.session.context.overridden,
              }}
              label="Context Manager"
            />
          )}
        </ModuleSection>
      )}

      {/* Providers */}
      {bundle.providers.length > 0 && (
        <ModuleSection
          icon={<Server className="h-4 w-4" />}
          title={`Providers (${bundle.providers.length})`}
        >
          {bundle.providers.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Tools */}
      {bundle.tools.length > 0 && (
        <ModuleSection
          icon={<Wrench className="h-4 w-4" />}
          title={`Tools (${bundle.tools.length})`}
        >
          {bundle.tools.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Hooks */}
      {bundle.hooks.length > 0 && (
        <ModuleSection
          icon={<Zap className="h-4 w-4" />}
          title={`Hooks (${bundle.hooks.length})`}
        >
          {bundle.hooks.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* Agents */}
      {bundle.agents.length > 0 && (
        <ModuleSection
          icon={<Bot className="h-4 w-4" />}
          title={`Agents (${bundle.agents.length})`}
        >
          {bundle.agents.map((mod) => (
            <ModuleItem key={mod.module} module={mod} />
          ))}
        </ModuleSection>
      )}

      {/* System Instruction */}
      {bundle.instruction && (
        <ModuleSection
          icon={<FileText className="h-4 w-4" />}
          title="System Instruction"
        >
          <pre className="text-xs bg-muted text-foreground p-3 rounded overflow-x-auto whitespace-pre-wrap">
            {bundle.instruction}
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
