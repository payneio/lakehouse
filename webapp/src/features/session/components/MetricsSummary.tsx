import {} from 'react';
import { Wrench, Clock, Brain, Trophy } from 'lucide-react';
import type { SessionMetrics } from '../types/execution';

interface MetricsSummaryProps {
  metrics: SessionMetrics;
}

export function MetricsSummary({ metrics }: MetricsSummaryProps) {
  return (
    <div className="bg-gray-50 rounded-lg p-4 mb-4">
      <div className="text-sm font-medium text-muted-foreground mb-3">Session Metrics</div>
      <div className="grid grid-cols-2 gap-3">
        {/* Total Tools */}
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-blue-600" />
          <div>
            <div className="text-lg font-semibold">{metrics.totalTools}</div>
            <div className="text-xs text-muted-foreground">Tools</div>
          </div>
        </div>

        {/* Average Duration */}
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-green-600" />
          <div>
            <div className="text-lg font-semibold">
              {metrics.avgToolDuration > 0 ? `${Math.round(metrics.avgToolDuration)}ms` : '-'}
            </div>
            <div className="text-xs text-muted-foreground">Avg Time</div>
          </div>
        </div>

        {/* Thinking Blocks */}
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-yellow-600" />
          <div>
            <div className="text-lg font-semibold">{metrics.totalThinking}</div>
            <div className="text-xs text-muted-foreground">Thinking</div>
          </div>
        </div>

        {/* Longest Tool */}
        <div className="flex items-center gap-2">
          <Trophy className="h-4 w-4 text-purple-600" />
          <div>
            <div className="text-lg font-semibold">
              {metrics.longestTool ? `${Math.round(metrics.longestTool.duration)}ms` : '-'}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {metrics.longestTool ? metrics.longestTool.name : 'N/A'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
