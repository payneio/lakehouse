import React from 'react';
import { CheckCircle, Circle, AlertCircle, Loader2, Zap } from 'lucide-react';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { ToolCall } from '../types/execution';

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

  // Format arguments for display
  const formatArguments = (args?: Record<string, unknown>) => {
    if (!args) return 'None';
    return JSON.stringify(args, null, 2);
  };

  // Format result for display
  const formatResult = (result?: unknown) => {
    if (result === undefined) return 'Pending...';
    if (typeof result === 'string') return result;
    return JSON.stringify(result, null, 2);
  };

  // Get first line of result for summary
  const resultSummary = React.useMemo(() => {
    const formatted = formatResult(tool.result);
    const firstLine = formatted.split('\n')[0];
    return firstLine.length > 100 ? firstLine.substring(0, 100) + '...' : firstLine;
  }, [tool.result]);

  const hasFullResult = formatResult(tool.result).length > resultSummary.length;

  return (
    <div className={cn('border-l-2 pl-3 py-2', tool.isSubAgent ? 'border-purple-400' : 'border-gray-200')}>
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger className="w-full text-left">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className={cn('flex-shrink-0', status.color)}>{status.icon}</span>
              <span className="font-medium truncate">{tool.name}</span>
              {tool.isSubAgent && tool.subAgentName && (
                <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                  {tool.subAgentName}
                </span>
              )}
            </div>
            <span className="text-sm text-muted-foreground flex-shrink-0">{durationText}</span>
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
