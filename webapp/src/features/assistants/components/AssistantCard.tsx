import { Package, ChevronRight, Server, Wrench, Zap, Bot } from 'lucide-react';
import type { AssistantListItem } from '@/api/assistants';

interface AssistantCardProps {
  assistant: AssistantListItem;
  onView: (assistant: AssistantListItem) => void;
}

export function AssistantCard({ assistant, onView }: AssistantCardProps) {
  const isUserAssistant = assistant.source === 'user';

  return (
    <div
      onClick={() => onView(assistant)}
      className="flex flex-col p-4 border rounded-lg hover:bg-accent/50 hover:border-primary/30 transition-colors cursor-pointer h-full"
    >
      {/* Header with icon and badges */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <Package className="h-8 w-8 text-primary/70 shrink-0" />
        <div className="flex flex-col items-end gap-1">
          <span
            className={`px-1.5 py-0.5 text-xs rounded ${
              isUserAssistant ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'
            }`}
          >
            {isUserAssistant ? 'User' : 'System'}
          </span>
          <span className="text-xs text-muted-foreground">v{assistant.version}</span>
        </div>
      </div>

      {/* Name */}
      <h3 className="font-medium text-sm truncate" title={assistant.name}>
        {assistant.name}
      </h3>

      {/* Description */}
      {assistant.description && (
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{assistant.description}</p>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-3 mt-auto pt-3 text-xs text-muted-foreground border-t border-border/50">
        {assistant.providerCount > 0 && (
          <span className="flex items-center gap-1" title="Providers">
            <Server className="h-3 w-3" />
            {assistant.providerCount}
          </span>
        )}
        {assistant.toolCount > 0 && (
          <span className="flex items-center gap-1" title="Tools">
            <Wrench className="h-3 w-3" />
            {assistant.toolCount}
          </span>
        )}
        {assistant.hookCount > 0 && (
          <span className="flex items-center gap-1" title="Hooks">
            <Zap className="h-3 w-3" />
            {assistant.hookCount}
          </span>
        )}
        {assistant.agentCount > 0 && (
          <span className="flex items-center gap-1" title="Agents">
            <Bot className="h-3 w-3" />
            {assistant.agentCount}
          </span>
        )}
      </div>

      {/* Extends info */}
      {assistant.includes.length > 0 && (
        <div className="flex items-center gap-1 mt-2 text-xs text-blue-600">
          <ChevronRight className="h-3 w-3 shrink-0" />
          <span className="truncate" title={assistant.includes.join(', ')}>
            {assistant.includes.join(', ')}
          </span>
        </div>
      )}
    </div>
  );
}
