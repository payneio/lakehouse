import React, { useState, useEffect } from 'react';
import { useEventStream } from '@/hooks/useEventStream';
import { BASE_URL } from '@/api/client';

interface ApprovalPrompt {
  approval_id: string;
  prompt: string;
  options: string[];
  timeout?: number;
}

interface ApprovalDialogProps {
  sessionId: string;
}

export function ApprovalDialog({ sessionId }: ApprovalDialogProps) {
  const [prompt, setPrompt] = useState<ApprovalPrompt | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const eventStream = useEventStream({ sessionId });

  useEffect(() => {
    return eventStream.on('hook:approval:required', (data) => {
      setPrompt({
        approval_id: data.approval_id || data.hook_data?.approval_id,
        prompt: data.prompt || data.hook_data?.approval_prompt || 'Approval required',
        options: data.options || data.hook_data?.approval_options || ['Allow', 'Deny'],
        timeout: data.timeout || data.hook_data?.approval_timeout,
      });
    });
  }, [eventStream]);

  const handleResponse = async (option: string) => {
    if (!prompt) return;

    setSubmitting(true);
    try {
      const response = await fetch(
        `${BASE_URL}/api/v1/sessions/${sessionId}/approval-response`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            approval_id: prompt.approval_id,
            response: option,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to submit approval response');
      }

      setPrompt(null);
    } catch (error) {
      console.error('Error submitting approval:', error);
    } finally {
      setSubmitting(false);
    }
  };

  if (!prompt) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          Approval Required
        </h2>

        <p className="text-gray-700 dark:text-gray-300 mb-6">
          {prompt.prompt}
        </p>

        <div className="flex gap-3 justify-end">
          {prompt.options.map((option) => (
            <button
              key={option}
              onClick={() => handleResponse(option)}
              disabled={submitting}
              className={`px-4 py-2 rounded-md font-medium transition-colors ${
                option.toLowerCase().includes('deny') || option.toLowerCase().includes('cancel')
                  ? 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white'
                  : 'bg-blue-500 hover:bg-blue-600 text-white'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {submitting ? 'Submitting...' : option}
            </button>
          ))}
        </div>

        {prompt.timeout && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-4">
            Timeout in {Math.floor(prompt.timeout / 60)} minutes
          </p>
        )}
      </div>
    </div>
  );
}
