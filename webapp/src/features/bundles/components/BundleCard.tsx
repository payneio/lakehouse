import { Package, ChevronRight, Copy, Eye, Trash2, Pencil, Server, Wrench, Zap, Bot } from 'lucide-react';
import type { BundleListItem } from '@/api/bundles';

interface BundleCardProps {
  bundle: BundleListItem;
  onView: (bundle: BundleListItem) => void;
  onCopy: (bundle: BundleListItem) => void;
  onEdit?: (bundle: BundleListItem) => void;
  onDelete?: (bundle: BundleListItem) => void;
}

export function BundleCard({ bundle, onView, onCopy, onEdit, onDelete }: BundleCardProps) {
  const isUserBundle = bundle.source === 'user';

  return (
    <div className="flex items-start gap-3 p-4 border rounded-lg hover:bg-accent/50 transition-colors">
      <Package className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{bundle.name}</span>
          <span className="text-xs text-muted-foreground">v{bundle.version}</span>
          <span
            className={`px-1.5 py-0.5 text-xs rounded ${
              isUserBundle
                ? 'bg-green-100 text-green-700'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            {isUserBundle ? 'User' : 'System'}
          </span>
        </div>

        {bundle.description && (
          <div className="text-sm text-muted-foreground mt-1">{bundle.description}</div>
        )}

        {/* Quick Stats */}
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
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
          {bundle.includes.length > 0 && (
            <span className="flex items-center gap-1 text-blue-600">
              <ChevronRight className="h-3 w-3" />
              Extends: {bundle.includes.join(', ')}
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onView(bundle)}
          className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
          title="View bundle details"
        >
          <Eye className="h-4 w-4" />
        </button>
        <button
          onClick={() => onCopy(bundle)}
          className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
          title="Copy to user bundles"
        >
          <Copy className="h-4 w-4" />
        </button>
        {isUserBundle && onEdit && (
          <button
            onClick={() => onEdit(bundle)}
            className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground"
            title="Edit bundle"
          >
            <Pencil className="h-4 w-4" />
          </button>
        )}
        {isUserBundle && onDelete && (
          <button
            onClick={() => onDelete(bundle)}
            className="p-2 rounded-md hover:bg-accent text-red-500 hover:text-red-600"
            title="Delete bundle"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
