import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { SessionMessage } from '@/types/api';
import type { CurrentActivity, ThinkingBlock } from '@/features/session/types/execution';
import { User, Bot } from 'lucide-react';
import { CurrentActivityIndicator } from './CurrentActivityIndicator';
import { ThinkingViewer } from './ThinkingViewer';

interface MessageListProps {
  messages: SessionMessage[];
  streamingContent?: string;
  currentActivity?: CurrentActivity | null;
  currentTurnThinking?: ThinkingBlock[];
}

export function MessageList({
  messages,
  streamingContent,
  currentActivity,
  currentTurnThinking = []
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Use instant scroll during streaming to prevent competing animations
    // Smooth scroll for static messages provides polish without interference
    const behavior = streamingContent ? 'instant' : 'smooth';
    bottomRef.current?.scrollIntoView({ behavior });
  }, [messages, streamingContent]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        No messages yet. Start chatting!
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {messages.map((message, idx) => {
        const isUser = message.role === 'user';
        return (
          <div
            key={idx}
            className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            {!isUser && (
              <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary" />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                isUser
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}
            >
              <div className={isUser ? '' : 'prose prose-sm dark:prose-invert max-w-none'}>
                {isUser ? (
                  <div className="whitespace-pre-wrap break-words">{message.content}</div>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                )}
              </div>
              <div className="text-xs opacity-70 mt-1">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
            {isUser && (
              <div className="shrink-0 h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                <User className="h-4 w-4 text-primary-foreground" />
              </div>
            )}
          </div>
        );
      })}

      {/* Show streaming content as it arrives */}
      {streamingContent && (
        <div className="flex gap-3 justify-start">
          <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary animate-pulse" />
          </div>
          <div className="max-w-[80%] space-y-2">
            <div
              className="rounded-lg p-3 bg-muted will-change-contents transition-[height] duration-75"
              style={{ contain: 'layout style' }}
            >
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingContent}
                </ReactMarkdown>
              </div>
              <div className="text-xs opacity-70 mt-1">Streaming...</div>
            </div>

            {/* Show thinking blocks if present */}
            {currentTurnThinking.length > 0 && (
              <ThinkingViewer
                thinking={currentTurnThinking}
                inline={true}
                defaultExpanded={false}
              />
            )}
          </div>
        </div>
      )}

      {/* Show current activity indicator (even when not streaming) */}
      {currentActivity && !streamingContent && (
        <div className="flex gap-3 justify-start">
          <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary animate-pulse" />
          </div>
          <div className="max-w-[80%]">
            <CurrentActivityIndicator activity={currentActivity} />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
