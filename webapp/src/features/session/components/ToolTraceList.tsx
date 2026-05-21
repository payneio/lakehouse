import {} from 'react';
import type { ToolCall } from '../types/execution';
import { ToolCallItem } from './ToolCallItem';

interface ToolTraceListProps {
  tools: ToolCall[];
}

export function ToolTraceList({ tools }: ToolTraceListProps) {
  if (tools.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2">No tools executed in this turn</div>
    );
  }

  return (
    <div className="space-y-2">
      {tools.map((tool) => (
        <ToolCallItem key={tool.id} tool={tool} />
      ))}
    </div>
  );
}
