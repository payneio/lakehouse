import { useState, useRef, type KeyboardEvent, type ChangeEvent } from 'react';
import { Send, Square } from 'lucide-react';
import { useMentionCompletion } from '@/hooks/useMentionCompletion';
import { FileCompletionDropdown } from '@/components/FileCompletionDropdown';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isSending?: boolean;
  onCancel?: () => void;
  amplifiedDir?: string;
}

export function MessageInput({
  onSend,
  disabled,
  isSending,
  onCancel,
  amplifiedDir = '',
}: MessageInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    mentionState,
    completions,
    isLoading,
    selectedIndex,
    handleInputChange,
    handleKeyDown: handleMentionKeyDown,
    selectCompletion,
    resetMention,
  } = useMentionCompletion({
    basePath: amplifiedDir,
    enabled: !!amplifiedDir,
  });

  const handleSend = () => {
    if (!input.trim() || disabled || isSending) return;
    onSend(input);
    setInput('');
    resetMention();
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPosition = e.target.selectionStart ?? value.length;
    setInput(value);
    handleInputChange(value, cursorPosition);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Handle mention completion keyboard navigation first
    if (mentionState.isActive) {
      const result = handleMentionKeyDown(e);
      if (result.handled) {
        if (result.selectedEntry) {
          // Insert the selected completion
          const replacement = selectCompletion(result.selectedEntry);
          const beforeMention = input.substring(0, mentionState.startIndex);
          const afterCursor = input.substring(
            mentionState.startIndex + mentionState.query.length + 1
          );
          const newValue = beforeMention + replacement + afterCursor;
          setInput(newValue);

          // If it's a directory, keep mention active for continued navigation
          if (result.selectedEntry.is_directory) {
            // Update cursor position after React re-renders
            setTimeout(() => {
              if (textareaRef.current) {
                const newCursorPos = beforeMention.length + replacement.length;
                textareaRef.current.selectionStart = newCursorPos;
                textareaRef.current.selectionEnd = newCursorPos;
                // Trigger mention detection at new cursor position
                handleInputChange(newValue, newCursorPos);
              }
            }, 0);
          } else {
            // File selected - add space and close mention
            const withSpace = beforeMention + replacement + ' ' + afterCursor;
            setInput(withSpace);
            resetMention();
          }
        }
        return;
      }
    }

    // Regular Enter to send
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCompletionSelect = (entry: typeof completions[0]) => {
    const replacement = selectCompletion(entry);
    const beforeMention = input.substring(0, mentionState.startIndex);
    const afterCursor = input.substring(
      mentionState.startIndex + mentionState.query.length + 1
    );

    if (entry.is_directory) {
      // Directory - insert and continue navigation
      const newValue = beforeMention + replacement + afterCursor;
      setInput(newValue);
      // Focus and update mention state
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          const newCursorPos = beforeMention.length + replacement.length;
          textareaRef.current.selectionStart = newCursorPos;
          textareaRef.current.selectionEnd = newCursorPos;
          handleInputChange(newValue, newCursorPos);
        }
      }, 0);
    } else {
      // File - insert with space and close
      const newValue = beforeMention + replacement + ' ' + afterCursor;
      setInput(newValue);
      resetMention();
      textareaRef.current?.focus();
    }
  };

  return (
    <div className="border-t p-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          {/* File completion dropdown */}
          {mentionState.isActive && (
            <FileCompletionDropdown
              entries={completions}
              selectedIndex={selectedIndex}
              isLoading={isLoading}
              onSelect={handleCompletionSelect}
            />
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={
              amplifiedDir
                ? 'Type your message... (@ for file completion, Enter to send)'
                : 'Type your message... (Enter to send, Shift+Enter for new line)'
            }
            disabled={disabled && !isSending}
            className="w-full resize-none rounded-md border px-3 py-2 min-h-[80px] max-h-[200px] disabled:opacity-50"
            rows={3}
          />
        </div>
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
