import React from 'react';
import { Brain, Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { cn } from '@/lib/utils';
import type { Turn, ToolCall, ThinkingBlock } from '../types/execution';
import { ToolCallItem } from './ToolCallItem';

interface TurnItemProps {
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

// Collapsible thinking block display
function ThinkingItem({ thinking }: { thinking: ThinkingBlock }) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const preview = thinking.content.length > 150
    ? thinking.content.substring(0, 150) + '...'
    : thinking.content;
  const hasMore = thinking.content.length > 150;

  return (
    <div className="border-l-2 border-amber-300 pl-3 py-2 bg-amber-50/50 rounded-r">
      <div className="flex items-start gap-2">
        <Brain className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-amber-900">
            {isExpanded ? thinking.content : preview}
          </div>
          {hasMore && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-xs text-amber-700 hover:text-amber-900 mt-1"
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function TurnItem({ turn, turnNumber }: TurnItemProps) {
  // Calculate duration - use state for live updates on active turns
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

  // Status display
  const getStatusDisplay = () => {
    switch (turn.status) {
      case 'waiting':
        return {
          icon: <Clock className="h-4 w-4" />,
          color: 'text-gray-400',
          label: 'Waiting',
        };
      case 'active':
        return {
          icon: <Loader2 className="h-4 w-4 animate-spin" />,
          color: 'text-blue-600',
          label: 'Active',
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
  const durationText = `${(duration / 1000).toFixed(1)}s`;

  // Truncate user message for display (handle undefined for legacy data)
  const userMessage = turn.userMessage ?? '';
  const displayMessage = userMessage.length > 50
    ? userMessage.substring(0, 50) + '...'
    : userMessage;

  return (
    <AccordionItem value={turn.id}>
      <AccordionTrigger className="hover:no-underline">
        <div className="flex items-start gap-2 flex-1 min-w-0 overflow-hidden">
          <span className={cn('flex-shrink-0 mt-0.5', status.color)}>{status.icon}</span>
          <div className="flex-1 min-w-0 text-left overflow-hidden">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium truncate">Turn {turnNumber}</span>
              <div className="flex items-center gap-2 flex-shrink-0 text-sm">
                <span className="text-muted-foreground whitespace-nowrap">{durationText}</span>
                <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded whitespace-nowrap">
                  {turn.tools.length} {turn.tools.length === 1 ? 'tool' : 'tools'}
                </span>
              </div>
            </div>
            <div className="text-sm text-muted-foreground truncate">"{displayMessage}"</div>
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent>
        <div className="space-y-4">
          {/* Full user message */}
          {userMessage.length > 50 && (
            <div className="text-sm">
              <div className="font-medium text-muted-foreground mb-1">User Message:</div>
              <div className="bg-gray-50 p-2 rounded">{userMessage}</div>
            </div>
          )}

          {/* Activity timeline - tools and thinking interspersed by timestamp */}
          <div>
            <div className="font-medium text-sm text-muted-foreground mb-2">
              Activity Timeline ({turn.tools.length} tools, {turn.thinking.length} thinking)
            </div>
            <div className="space-y-2">
              {mergeActivities(turn.tools, turn.thinking).map((activity) =>
                activity.type === 'tool' ? (
                  <ToolCallItem key={activity.data.id} tool={activity.data} />
                ) : (
                  <ThinkingItem key={activity.data.id} thinking={activity.data} />
                )
              )}
            </div>
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
