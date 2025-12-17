/**
 * Execution state management hook
 *
 * Manages execution traces for sessions including:
 * - Tool calls with timing
 * - Thinking blocks
 * - Turn lifecycle
 * - Performance metrics
 *
 * Uses refs to avoid re-render issues during high-frequency SSE updates
 */

import { useRef, useCallback, useMemo, useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/api/client';
import type {
  ExecutionState,
  Turn,
  ToolCall,
  ThinkingBlock,
  SessionMetrics,
  CurrentActivity,
} from '../types/execution';

// Browser-compatible UUID generation (crypto.randomUUID may not be available in all contexts)
function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}-${Math.random().toString(36).substring(2, 11)}`;
}

interface ExecutionTraceResponse {
  turns: Turn[];
}

interface UseExecutionStateOptions {
  sessionId: string;
}

export function useExecutionState({ sessionId }: UseExecutionStateOptions) {
  // Use ref to avoid re-renders during SSE updates
  const stateRef = useRef<ExecutionState>({
    turns: [],
    currentTurn: null,
    metrics: {
      totalTools: 0,
      totalThinking: 0,
      avgToolDuration: 0,
    },
  });

  // Track whether we've initialized from historical data
  const initializedRef = useRef(false);

  // Counter to force re-renders when state changes
  // This allows us to use refs for state (avoiding excessive re-renders during SSE)
  // while still triggering re-renders when consumers need fresh data
  const [updateCounter, setUpdateCounter] = useState(0);
  const forceUpdate = useCallback(() => {
    setUpdateCounter(c => c + 1);
  }, []);

  // Load historical trace on session open
  const { data: historicalTrace } = useQuery({
    queryKey: ['execution-trace', sessionId],
    queryFn: () =>
      fetchApi<ExecutionTraceResponse>(`/api/v1/sessions/${sessionId}/execution-trace`),
    enabled: !!sessionId,
    staleTime: Infinity, // Historical data doesn't change
  });

  // Initialize state with historical trace (in effect, not during render)
  useEffect(() => {
    if (historicalTrace?.turns && !initializedRef.current) {
      stateRef.current.turns = historicalTrace.turns;
      initializedRef.current = true;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Intentional: sync ref state to React after async data load
      forceUpdate();
    }
  }, [historicalTrace, forceUpdate]);

  // Calculate metrics from current state
  const calculateMetrics = useCallback((): SessionMetrics => {
    const allTools = stateRef.current.turns.flatMap((t) => t.tools);
    const completedTools = allTools.filter((t) => t.duration !== undefined);
    const allThinking = stateRef.current.turns.flatMap((t) => t.thinking);

    const avgDuration =
      completedTools.length > 0
        ? completedTools.reduce((sum, t) => sum + (t.duration || 0), 0) / completedTools.length
        : 0;

    const longest = completedTools.reduce<{ name: string; duration: number } | undefined>(
      (max, tool) => {
        if (!tool.duration) return max;
        if (!max || tool.duration > max.duration) {
          return { name: tool.name, duration: tool.duration };
        }
        return max;
      },
      undefined
    );

    return {
      totalTools: allTools.length,
      totalThinking: allThinking.length,
      avgToolDuration: avgDuration,
      longestTool: longest,
    };
  }, []);

  // Start new turn
  const startTurn = useCallback((userMessage: string) => {
    const turn: Turn = {
      id: generateId(),
      userMessage,
      assistantMessageId: null,
      status: 'active',
      tools: [],
      thinking: [],
      startTime: Date.now(),
    };

    stateRef.current.currentTurn = turn;
    stateRef.current.turns.push(turn);
    forceUpdate();
  }, [forceUpdate]);

  // Complete current turn
  const completeTurn = useCallback(() => {
    if (stateRef.current.currentTurn) {
      stateRef.current.currentTurn.status = 'completed';
      stateRef.current.currentTurn.endTime = Date.now();
      stateRef.current.currentTurn = null;
      stateRef.current.metrics = calculateMetrics();
      forceUpdate();
    }
  }, [calculateMetrics, forceUpdate]);

  // Add tool to current turn
  const addTool = useCallback(
    (toolName: string, toolInput?: Record<string, unknown>, parallelGroupId?: string) => {
      if (!stateRef.current.currentTurn) {
        return;
      }

      // Detect sub-agent calls
      const isSubAgent = toolName === 'Task';
      const subAgentName = isSubAgent ? (toolInput?.subagent_type as string) : undefined;

      const tool: ToolCall = {
        id: generateId(),
        name: toolName,
        parallelGroupId,
        status: 'starting',
        startTime: Date.now(),
        arguments: toolInput,
        isSubAgent,
        subAgentName,
      };

      stateRef.current.currentTurn.tools.push(tool);
      forceUpdate();
    },
    [forceUpdate]
  );

  // Update tool status
  const updateTool = useCallback(
    (toolName: string, parallelGroupId: string | undefined, updates: Partial<ToolCall>) => {
      if (!stateRef.current.currentTurn) {
        return;
      }

      // Match by tool name + parallel group ID (and only unfinished tools)
      const tool = stateRef.current.currentTurn.tools.find((t) => {
        const nameMatches = t.name === toolName;
        const groupMatches = parallelGroupId
          ? t.parallelGroupId === parallelGroupId
          : true; // If no parallelGroupId, match by name only
        const isUnfinished = t.status === 'starting' || t.status === 'running';

        return nameMatches && groupMatches && isUnfinished;
      });

      if (tool) {
        Object.assign(tool, updates);

        // Calculate duration if endTime is set
        if (updates.endTime) {
          tool.duration = updates.endTime - tool.startTime;
        }

        // Update metrics if tool completed
        if (updates.status === 'completed' || updates.status === 'error') {
          stateRef.current.metrics = calculateMetrics();
        }

        forceUpdate();
      }
    },
    [calculateMetrics, forceUpdate]
  );

  // Add thinking block to current turn
  const addThinking = useCallback((content: string) => {
    if (!stateRef.current.currentTurn) return;

    const thinking: ThinkingBlock = {
      id: generateId(),
      content,
      timestamp: Date.now(),
    };

    stateRef.current.currentTurn.thinking.push(thinking);
    stateRef.current.metrics = calculateMetrics();
    forceUpdate();
  }, [calculateMetrics, forceUpdate]);

  // Get current activity (for inline display)
  const getCurrentActivity = useCallback((): CurrentActivity | null => {
    const currentTurn = stateRef.current.currentTurn;
    if (!currentTurn) return null;

    // Check for active tool
    const activeTool = currentTurn.tools.find(
      (t) => t.status === 'starting' || t.status === 'running'
    );

    if (activeTool) {
      if (activeTool.isSubAgent) {
        return {
          type: 'subagent',
          subAgentName: activeTool.subAgentName,
          toolName: activeTool.name,
          args: activeTool.arguments,
        };
      }
      return {
        type: 'tool',
        toolName: activeTool.name,
        args: activeTool.arguments,
      };
    }

    // Check for recent thinking
    if (currentTurn.thinking.length > 0) {
      return { type: 'thinking' };
    }

    return null;
  }, []);

  // Get current state (safe getter function)
  // Return a NEW object reference when updateCounter changes, so React re-renders children
  const getState = useCallback(() => ({
    ...stateRef.current,
    turns: [...stateRef.current.turns],  // New array reference for proper React diffing
  }), [updateCounter]);

  // Return stable API using useMemo
  return useMemo(
    () => ({
      getState,
      startTurn,
      completeTurn,
      addTool,
      updateTool,
      addThinking,
      getCurrentActivity,
    }),
    [getState, startTurn, completeTurn, addTool, updateTool, addThinking, getCurrentActivity]
  );
}
