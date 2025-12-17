import React from 'react';
import { Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { cn } from '@/lib/utils';
import type { Turn } from '../types/execution';
import { ToolTraceList } from './ToolTraceList';

interface TurnItemProps {
  turn: Turn;
  turnNumber: number;
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
  const durationText = `${duration}ms`;

  // Truncate user message for display (handle undefined for legacy data)
  const userMessage = turn.userMessage ?? '';
  const displayMessage = userMessage.length > 50
    ? userMessage.substring(0, 50) + '...'
    : userMessage;

  return (
    <AccordionItem value={turn.id}>
      <AccordionTrigger className="hover:no-underline">
        <div className="flex items-start justify-between gap-2 flex-1 pr-2">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            <span className={cn('flex-shrink-0 mt-0.5', status.color)}>{status.icon}</span>
            <div className="flex-1 min-w-0 text-left">
              <div className="font-medium">Turn {turnNumber}</div>
              <div className="text-sm text-muted-foreground truncate">"{displayMessage}"</div>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0 text-sm">
            <span className="text-muted-foreground">{durationText}</span>
            <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
              {turn.tools.length} {turn.tools.length === 1 ? 'tool' : 'tools'}
            </span>
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

          {/* Tool trace */}
          <div>
            <div className="font-medium text-sm text-muted-foreground mb-2">Tools Executed:</div>
            <ToolTraceList tools={turn.tools} />
          </div>

          {/* Thinking blocks (if any) */}
          {turn.thinking.length > 0 && (
            <div>
              <div className="font-medium text-sm text-muted-foreground mb-2">
                Thinking ({turn.thinking.length} blocks)
              </div>
              <div className="bg-yellow-50 p-3 rounded text-sm space-y-2">
                {turn.thinking.map((block) => (
                  <div key={block.id} className="text-yellow-900">
                    {block.content}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}
