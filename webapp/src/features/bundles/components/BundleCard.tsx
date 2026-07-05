import { Package, ChevronRight, Server, Wrench, Zap, Bot } from 'lucide-react';
import type { BundleListItem } from '@/api/bundles';

interface BundleCardProps {
  bundle: BundleListItem;
  onView: (bundle: BundleListItem) => void;
}

export function BundleCard({ bundle, onView }: BundleCardProps) {
  const isUserBundle = bundle.source === 'user';

  return (
    <div
      onClick={() => onView(bundle)}
      className="flex flex-col p-4 border rounded-lg hover:bg-accent/50 hover:border-primary/30 transition-colors cursor-pointer h-full"
    >
      {/* Header with icon and badges */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <Package className="h-8 w-8 text-primary/70 shrink-0" />
        <div className="flex flex-col items-end gap-1">
          <span
            className={`px-1.5 py-0.5 text-xs rounded ${
              isUserBundle ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'
            }`}
          >
            {isUserBundle ? 'User' : 'System'}
          </span>
          <span className="text-xs text-muted-foreground">v{bundle.version}</span>
        </div>
      </div>

      {/* Name */}
      <h3 className="font-medium text-sm truncate" title={bundle.name}>
        {bundle.name}
      </h3>

      {/* Description */}
      {bundle.description && (
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{bundle.description}</p>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-3 mt-auto pt-3 text-xs text-muted-foreground border-t border-border/50">
        {bundle.providerCount > 0 && (
          <span className="flex items-center gap-1" title="Providers">
            <Server className="h-3 w-3" />
            {bundle.providerCount}
          </span>
        )}
        {bundle.toolCount > 0 && (
          <span className="flex items-center gap-1" title="Tools">
            <Wrench className="h-3 w-3" />
            {bundle.toolCount}
          </span>
        )}
        {bundle.hookCount > 0 && (
          <span className="flex items-center gap-1" title="Hooks">
            <Zap className="h-3 w-3" />
            {bundle.hookCount}
          </span>
        )}
        {bundle.agentCount > 0 && (
          <span className="flex items-center gap-1" title="Agents">
            <Bot className="h-3 w-3" />
            {bundle.agentCount}
          </span>
        )}
      </div>

      {/* Extends info */}
      {bundle.includes.length > 0 && (
        <div className="flex items-center gap-1 mt-2 text-xs text-blue-600">
          <ChevronRight className="h-3 w-3 shrink-0" />
          <span className="truncate" title={bundle.includes.join(', ')}>
            {bundle.includes.join(', ')}
          </span>
        </div>
      )}
    </div>
  );
}
