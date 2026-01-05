import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { SessionMessage } from '@/types/api';
import type { CurrentActivity, ThinkingBlock } from '@/features/session/types/execution';
import { User, Bot, Trash2, Copy, Check } from 'lucide-react';
import { CurrentActivityIndicator } from './CurrentActivityIndicator';
import { ThinkingViewer } from './ThinkingViewer';

interface MessageListProps {
  messages: SessionMessage[];
  streamingContent?: string;
  currentActivity?: CurrentActivity | null;
  currentTurnThinking?: ThinkingBlock[];
  onContainerMount?: (element: HTMLDivElement | null) => void;
  onDeleteLast?: () => void;
  canDeleteLast?: boolean;
}

export function MessageList({
  messages,
  streamingContent,
  currentActivity,
  currentTurnThinking = [],
  onContainerMount,
  onDeleteLast,
  canDeleteLast = false,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = async (content: string, index: number) => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(content);
      } else {
        // Fallback for mobile/non-secure contexts using execCommand
        const textArea = document.createElement('textarea');
        textArea.value = content;
        // Avoid scrolling to bottom on mobile
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (!successful) {
          throw new Error('execCommand copy failed');
        }
      }
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

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
    <div ref={onContainerMount} className="flex-1 overflow-y-auto space-y-4 p-4 pt-[88px] lg:pt-4">
      {messages.map((message, idx) => {
        const isUser = message.role === 'user';
        const isLastMessage = idx === messages.length - 1;
        const showDeleteButton = isLastMessage && onDeleteLast && canDeleteLast;
        return (
          <div
            key={idx}
            className={`group flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            {!isUser && (
              <div className="shrink-0 h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary" />
              </div>
            )}
            <div className="flex flex-col gap-1 min-w-0 max-w-[80%]">
              <div
                className={`rounded-lg p-3 ${
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
              {/* Action bar - always visible on mobile, hover on desktop */}
              <div className={`flex gap-1 ${isUser ? 'justify-end' : 'justify-start'} opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-opacity`}>
                <button
                  onClick={() => handleCopy(message.content, idx)}
                  className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                  title="Copy message"
                >
                  {copiedIndex === idx ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
                {showDeleteButton && (
                  <button
                    onClick={onDeleteLast}
                    className="p-1.5 hover:bg-destructive/10 rounded text-muted-foreground hover:text-destructive"
                    title="Delete last message"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
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
