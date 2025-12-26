/**
 * Execution state types for session activity tracking
 *
 * Tracks tool calls, thinking blocks, and metrics across turns
 * following the specification in @working/improving-session-affordance.md
 */

export type ToolCallStatus = 'starting' | 'running' | 'completed' | 'error';
export type TurnStatus = 'waiting' | 'active' | 'completed' | 'error';

export interface ToolCall {
  id: string;
  name: string;
  parallelGroupId?: string; // For matching with backend events
  status: ToolCallStatus;
  startTime: number;
  endTime?: number;
  duration?: number;
  arguments?: Record<string, unknown>;
  result?: unknown;
  error?: string;
  isSubAgent?: boolean;
  subAgentName?: string;
  childSessionId?: string; // For Task tools, the subsession ID to link to
}

export interface ThinkingBlock {
  id: string;
  content: string;
  timestamp: number;
}

export interface Turn {
  id: string;
  userMessage: string;
  assistantMessageId: string | null;
  status: TurnStatus;
  tools: ToolCall[];
  thinking: ThinkingBlock[];
  startTime: number;
  endTime?: number;
}

export interface SessionMetrics {
  totalTools: number;
  totalThinking: number;
  avgToolDuration: number;
  longestTool?: {
    name: string;
    duration: number;
  };
}

export interface ExecutionState {
  turns: Turn[];
  currentTurn: Turn | null;
  metrics: SessionMetrics;
}

export interface CurrentActivity {
  type: 'thinking' | 'tool' | 'subagent';
  toolName?: string;
  subAgentName?: string;
  args?: Record<string, unknown>;
}
