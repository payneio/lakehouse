import { useState, useEffect } from 'react';

interface ToolStatus {
  name: string;
  status: 'starting' | 'executing' | 'completed' | 'error';
  args?: unknown;
  result?: unknown;
  error?: string;
}

interface HookEventData {
  hook_data?: {
    tool_name?: string;
    tool_input?: unknown;
    tool_response?: unknown;
    error?: string;
  };
}

interface ToolCallDisplayProps {
  sessionId: string;
  eventStream: {
    on: (eventType: string, handler: (data: unknown) => void) => () => void;
    emit: (eventType: string, data: unknown) => void;
    state: { status: string };
  };
}

export function ToolCallDisplay({ sessionId, eventStream }: ToolCallDisplayProps) {
  const [toolStatus, setToolStatus] = useState<ToolStatus | null>(null);

  useEffect(() => {
    console.log('[ToolCallDisplay] Setting up hook:tool:pre handler for:', sessionId);

    const unsubPre = eventStream.on('hook:tool:pre', (data) => {
      console.log('[ToolCallDisplay] hook:tool:pre received:', data);
      const hookData = data as HookEventData;
      const toolName = hookData.hook_data?.tool_name || 'Unknown Tool';
      const toolArgs = hookData.hook_data?.tool_input;

      setToolStatus({
        name: toolName,
        status: 'starting',
        args: toolArgs,
      });
    });

    const unsubPost = eventStream.on('hook:tool:post', (data) => {
      console.log('[ToolCallDisplay] hook:tool:post received:', data);
      const hookData = data as HookEventData;
      const toolName = hookData.hook_data?.tool_name || 'Unknown Tool';
      const toolResult = hookData.hook_data?.tool_response;
      const error = hookData.hook_data?.error;

      setToolStatus((prev) => ({
        name: toolName,
        status: error ? 'error' : 'completed',
        args: prev?.args,
        result: toolResult,
        error: error,
      }));

      setTimeout(() => setToolStatus(null), 3000);
    });

    return () => {
      unsubPre();
      unsubPost();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, eventStream.on]); // eventStream stable, only re-run on sessionId or on function change

  if (!toolStatus) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 rounded-md text-sm">
      {toolStatus.status === 'starting' && (
        <>
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span className="text-blue-700 dark:text-blue-300">
            Calling {toolStatus.name}...
          </span>
        </>
      )}

      {toolStatus.status === 'completed' && (
        <>
          <svg className="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-green-700 dark:text-green-300">
            {toolStatus.name} completed
          </span>
        </>
      )}

      {toolStatus.status === 'error' && (
        <>
          <svg className="h-4 w-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span className="text-red-700 dark:text-red-300">
            {toolStatus.name} failed: {toolStatus.error}
          </span>
        </>
      )}
    </div>
  );
}
