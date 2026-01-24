import { useState, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateSession } from '@/api/sessions';
import { Edit2 } from 'lucide-react';

interface SessionNameEditProps {
  sessionId: string;
  currentName?: string;
  createdAt: string;
}

export function SessionNameEdit({ sessionId, currentName, createdAt }: SessionNameEditProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(currentName || '');
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const displayName = currentName ||
    `Session from ${new Date(createdAt).toLocaleDateString()}`;

  const updateMutation = useMutation({
    mutationFn: (name: string) => updateSession(sessionId, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      queryClient.invalidateQueries({ queryKey: ['session', sessionId] });
      setIsEditing(false);
    },
  });

  const handleSave = () => {
    const trimmed = value.trim();
    if (trimmed !== (currentName || '')) {
      updateMutation.mutate(trimmed);
    } else {
      setIsEditing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    }
    if (e.key === 'Escape') {
      setValue(currentName || '');
      setIsEditing(false);
    }
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  if (isEditing) {
    return (
      <div className="flex-1">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          maxLength={200}
          className="w-full font-medium border-b-2 border-primary focus:outline-none bg-transparent"
          placeholder="Session name"
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-1 min-w-0">
      <span className="font-medium truncate">{displayName}</span>
      <button
        onClick={() => setIsEditing(true)}
        className="p-1 hover:bg-accent rounded shrink-0"
        title="Rename session"
      >
        <Edit2 className="h-3 w-3" />
      </button>
    </div>
  );
}
