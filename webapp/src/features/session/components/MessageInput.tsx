import { useState, type KeyboardEvent } from 'react';
import { Send, Square } from 'lucide-react';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isSending?: boolean;
  onCancel?: () => void;
}

export function MessageInput({ onSend, disabled, isSending, onCancel }: MessageInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t p-4">
      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          disabled={disabled}
          className="flex-1 resize-none rounded-md border px-3 py-2 min-h-[80px] max-h-[200px] disabled:opacity-50"
          rows={3}
        />
        {isSending && onCancel ? (
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90 h-fit"
            title="Cancel (Escape)"
          >
            <Square className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 h-fit"
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
