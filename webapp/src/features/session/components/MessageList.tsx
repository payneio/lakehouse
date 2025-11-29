import { useEffect, useRef } from 'react';
import type { SessionMessage } from '@/types/api';
import { User, Bot } from 'lucide-react';

interface MessageListProps {
  messages: SessionMessage[];
  streamingContent?: string;
}

export function MessageList({ messages, streamingContent }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
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
              <div className="whitespace-pre-wrap break-words">{message.content}</div>
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
          <div className="max-w-[80%] rounded-lg p-3 bg-muted">
            <div className="whitespace-pre-wrap break-words">{streamingContent}</div>
            <div className="text-xs opacity-70 mt-1">Streaming...</div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
