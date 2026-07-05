import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, Circle, AlertCircle, Loader2, Zap, ExternalLink, ListTodo } from 'lucide-react';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { ToolCall } from '../types/execution';
import { getToolPreview } from './toolPreview';

// ---- Todo tool: structured display ----

interface TodoItem {
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
  activeForm?: string;
}

/** Pull the todos array from result (authoritative) or arguments (fallback). */
function parseTodos(tool: ToolCall): TodoItem[] {
  // Try result first — it reflects the actual state after the operation
  let source: unknown = tool.result;
  if (typeof source === 'string') {
    try { source = JSON.parse(source); } catch { source = null; }
  }
  if (source && typeof source === 'object' && 'todos' in (source as Record<string, unknown>)) {
    const arr = (source as Record<string, unknown>).todos;
    if (Array.isArray(arr)) return arr as TodoItem[];
  }

  // Fall back to arguments (the request payload)
  if (tool.arguments?.todos && Array.isArray(tool.arguments.todos)) {
    return tool.arguments.todos as TodoItem[];
  }
  return [];
}

// Format arguments for display
function formatArguments(args?: Record<string, unknown>): string {
  if (!args) return 'None';
  return JSON.stringify(args, null, 2);
}

// Format result for display
function formatResult(result?: unknown): string {
  if (result === undefined) return 'Pending...';
  if (typeof result === 'string') return result;
  return JSON.stringify(result, null, 2);
}

function TodoToolDisplay({ tool }: { tool: ToolCall }) {
  const todos = React.useMemo(() => parseTodos(tool), [tool]);

  const counts = React.useMemo(() => {
    let done = 0, active = 0, pending = 0;
    for (const t of todos) {
      if (t.status === 'completed') done++;
      else if (t.status === 'in_progress') active++;
      else pending++;
    }
    return { done, active, pending, total: todos.length };
  }, [todos]);

  if (todos.length === 0) return null;

  return (
    <div className="border-l-2 border-gray-200 dark:border-gray-700 pl-3 py-2">
      {/* Compact header */}
      <div className="flex items-center gap-2 mb-1.5 text-xs text-muted-foreground">
        <ListTodo className="h-3.5 w-3.5 flex-shrink-0" />
        <span>
          {counts.done}/{counts.total} done
        </span>
      </div>

      {/* Todo items */}
      <div className="space-y-1">
        {todos.map((item, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            {item.status === 'completed' ? (
              <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
            ) : item.status === 'in_progress' ? (
              <Loader2 className="h-4 w-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0 mt-0.5" />
            ) : (
              <Circle className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
            )}
            <span
              className={cn(
                item.status === 'completed' && 'text-muted-foreground line-through',
                item.status === 'in_progress' && 'text-foreground font-medium',
              )}
            >
              {item.status === 'in_progress' && item.activeForm
                ? item.activeForm
                : item.content}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Generic tool call display ----

interface ToolCallItemProps {
  tool: ToolCall;
}

export function ToolCallItem({ tool }: ToolCallItemProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  // Log whenever tool prop changes
  React.useEffect(() => {
    console.log('[ToolCallItem] Rendering tool:', {
      id: tool.id,
      name: tool.name,
      status: tool.status,
      result: tool.result,
      duration: tool.duration
    });
  }, [tool]);

  // Get first line of result for summary.
  // Computed before any early return so hooks run in a stable order.
  const resultSummary = React.useMemo(() => {
    const formatted = formatResult(tool.result);
    const firstLine = formatted.split('\n')[0];
    return firstLine.length > 100 ? firstLine.substring(0, 100) + '...' : firstLine;
  }, [tool.result]);

  // Todo tool gets its own structured display
  if (tool.name === 'todo') {
    return <TodoToolDisplay tool={tool} />;
  }

  // Status icon and color
  const getStatusDisplay = () => {
    if (tool.isSubAgent) {
      return {
        icon: <Zap className="h-4 w-4" />,
        color: 'text-purple-600',
        label: tool.subAgentName || 'Sub-agent',
      };
    }

    switch (tool.status) {
      case 'starting':
        return {
          icon: <Circle className="h-4 w-4" />,
          color: 'text-gray-400',
          label: 'Starting',
        };
      case 'running':
        return {
          icon: <Loader2 className="h-4 w-4 animate-spin" />,
          color: 'text-blue-600',
          label: 'Running',
        };
      case 'completed':
        return {
          icon: <CheckCircle className="h-4 w-4" />,
          color: 'text-green-600',
          label: 'Completed',
        };
      case 'error':
        return {
          icon: <AlertCircle className="h-4 w-4" />,
          color: 'text-red-600',
          label: 'Error',
        };
    }
  };

  const status = getStatusDisplay();
  const durationText = tool.duration ? `${(tool.duration / 1000).toFixed(1)}s` : '...';

  const hasFullResult = formatResult(tool.result).length > resultSummary.length;

  return (
    <div className={cn('border-l-2 pl-3 py-2', tool.isSubAgent ? 'border-purple-400' : 'border-gray-200')}>
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger className="w-full text-left">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className={cn('flex-shrink-0', status.color)}>{status.icon}</span>
              <span className="font-medium flex-shrink-0">{tool.name}</span>
              {(() => {
                const preview = getToolPreview(tool);
                return preview ? (
                  <span className="text-muted-foreground truncate text-xs font-mono">
                    {preview}
                  </span>
                ) : null;
              })()}
              {tool.isSubAgent && tool.subAgentName && (
                <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                  {tool.subAgentName}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-sm text-muted-foreground">{durationText}</span>
              {tool.childSessionId && (
                <Link
                  to={`/projects/sessions/${tool.childSessionId}`}
                  onClick={(e) => e.stopPropagation()}
                  className="text-muted-foreground hover:text-foreground"
                  title="View subsession"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="mt-3 space-y-3 text-sm">
            {/* Status */}
            <div>
              <span className="font-medium text-muted-foreground">Status: </span>
              <span className={status.color}>{status.label}</span>
            </div>

            {/* Arguments */}
            {tool.arguments && (
              <div>
                <div className="font-medium text-muted-foreground mb-1">Arguments:</div>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
                  {formatArguments(tool.arguments)}
                </pre>
              </div>
            )}

            {/* Result */}
            <div>
              <div className="font-medium text-muted-foreground mb-1">Result:</div>
              {tool.error ? (
                <div className="bg-red-50 text-red-900 p-2 rounded text-xs">{tool.error}</div>
              ) : (
                <div className="bg-gray-50 p-2 rounded text-xs">
                  <div className="overflow-x-auto">
                    <pre>{isExpanded ? formatResult(tool.result) : resultSummary}</pre>
                  </div>
                  {hasFullResult && !isExpanded && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsExpanded(true);
                      }}
                      className="mt-2 text-blue-600 hover:underline text-xs"
                    >
                      Show Full Result
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
