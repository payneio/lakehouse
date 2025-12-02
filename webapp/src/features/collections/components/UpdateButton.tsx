import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CacheStatus } from '@/types/cache';

interface UpdateButtonProps {
  status: CacheStatus;
  onUpdate: () => void;
  isUpdating: boolean;
  size?: 'sm' | 'md';
}

export function UpdateButton({ status, onUpdate, isUpdating, size = 'sm' }: UpdateButtonProps) {
  if (status === 'fresh') return null;

  const sizeClasses = size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm';

  return (
    <button
      onClick={onUpdate}
      disabled={isUpdating}
      className={cn(
        'inline-flex items-center gap-1.5 border rounded-md hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        sizeClasses
      )}
    >
      <RefreshCw className={cn('h-3.5 w-3.5', isUpdating && 'animate-spin')} />
      <span>Update</span>
    </button>
  );
}
