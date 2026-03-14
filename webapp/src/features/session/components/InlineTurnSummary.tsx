import React from 'react';
import { Brain, CheckCircle, AlertCircle, Loader2, Clock, ChevronRight } from 'lucide-react';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { Turn, ToolCall, ThinkingBlock } from '../types/execution';
import { ToolCallItem } from './ToolCallItem';

interface InlineTurnSummaryProps {
  turn: Turn;
  turnNumber: number;
}

// Activity item for timeline rendering - either a tool call or thinking block
type ActivityItem =
  | { type: 'tool'; data: ToolCall; timestamp: number }
  | { type: 'thinking'; data: ThinkingBlock; timestamp: number };

// Merge tools and thinking blocks into a single timeline sorted by timestamp
function mergeActivities(tools: ToolCall[], thinking: ThinkingBlock[]): ActivityItem[] {
  const activities: ActivityItem[] = [
    ...tools.map((t) => ({ type: 'tool' as const, data: t, timestamp: t.startTime })),
    ...thinking.map((t) => ({ type: 'thinking' as const, data: t, timestamp: t.timestamp })),
  ];
  return activities.sort((a, b) => a.timestamp - b.timestamp);
}

// Collapsible thinking block display (inline version)
function InlineThinkingItem({ thinking }: { thinking: ThinkingBlock }) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const preview = thinking.content.length > 150
    ? thinking.content.substring(0, 150) + '...'
    : thinking.content;
  const hasMore = thinking.content.length > 150;

  return (
    <div className="border-l-2 border-amber-300 dark:border-amber-600 pl-3 py-2 bg-amber-50/50 dark:bg-amber-900/20 rounded-r">
      <div className="flex items-start gap-2">
        <Brain className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-xs text-amber-900 dark:text-amber-200">
            {isExpanded ? thinking.content : preview}
          </div>
          {hasMore && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-xs text-amber-700 dark:text-amber-400 hover:text-amber-900 dark:hover:text-amber-200 mt-1"
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function InlineTurnSummary({ turn, turnNumber }: InlineTurnSummaryProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  // Live duration tracking for active turns
  const [liveDuration, setLiveDuration] = React.useState(0);

  React.useEffect(() => {
    if (turn.status === 'active' && !turn.endTime) {
      const interval = setInterval(() => {
        setLiveDuration(Date.now() - turn.startTime);
      }, 100);
      return () => clearInterval(interval);
    }
  }, [turn.status, turn.endTime, turn.startTime]);

  const duration = turn.endTime
    ? Math.round(turn.endTime - turn.startTime)
    : Math.round(liveDuration);
  const durationText = `${(duration / 1000).toFixed(1)}s`;

  const isActive = turn.status === 'active';
  const isError = turn.status === 'error';
  const toolCount = turn.tools.length;

  // Status icon
  const statusIcon = (() => {
    switch (turn.status) {
      case 'waiting':
        return <Clock className="h-3.5 w-3.5 text-muted-foreground" />;
      case 'active':
        return <Loader2 className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />;
      case 'error':
        return <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />;
    }
  })();

  // Current tool name for active turns
  const activeToolName = isActive && turn.tools.length > 0
    ? turn.tools[turn.tools.length - 1]
    : null;
  const activeToolRunning = activeToolName && (activeToolName.status === 'starting' || activeToolName.status === 'running');

  const activities = mergeActivities(turn.tools, turn.thinking);

  return (
    <div className="flex justify-start w-full">
      <div className="max-w-[80%] w-full ml-11">
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger className="w-full text-left">
            <div
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-colors',
                'hover:bg-muted/80',
                isActive
                  ? 'bg-blue-50/50 dark:bg-blue-900/20 border border-blue-200/50 dark:border-blue-800/50'
                  : isError
                    ? 'bg-red-50/50 dark:bg-red-900/20 border border-red-200/50 dark:border-red-800/50'
                    : 'bg-muted/40 border border-transparent',
              )}
            >
              {/* Expand chevron */}
              <ChevronRight
                className={cn(
                  'h-3 w-3 text-muted-foreground transition-transform flex-shrink-0',
                  isExpanded && 'rotate-90',
                )}
              />

              {/* Status icon */}
              <span className="flex-shrink-0">{statusIcon}</span>

              {/* Active tool name or summary */}
              <span className="text-muted-foreground truncate flex-1">
                {isActive && activeToolRunning ? (
                  <>Calling <span className="font-medium text-foreground">{activeToolName.name}</span>...</>
                ) : isActive && toolCount === 0 ? (
                  'Working...'
                ) : (
                  <>Turn {turnNumber}</>
                )}
              </span>

              {/* Tool count badge */}
              {toolCount > 0 && (
                <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded-full text-muted-foreground flex-shrink-0 tabular-nums">
                  {toolCount} {toolCount === 1 ? 'tool' : 'tools'}
                </span>
              )}

              {/* Duration */}
              <span className="text-muted-foreground flex-shrink-0 tabular-nums">
                {durationText}
              </span>
            </div>
          </CollapsibleTrigger>

          <CollapsibleContent>
            <div className="mt-1 ml-1 space-y-1.5 pb-1">
              {activities.length === 0 ? (
                <div className="text-xs text-muted-foreground px-3 py-2">
                  {isActive ? 'Processing...' : 'No tool calls in this turn.'}
                </div>
              ) : (
                activities.map((activity) =>
                  activity.type === 'tool' ? (
                    <ToolCallItem key={activity.data.id} tool={activity.data} />
                  ) : (
                    <InlineThinkingItem key={activity.data.id} thinking={activity.data} />
                  )
                )
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  );
}
