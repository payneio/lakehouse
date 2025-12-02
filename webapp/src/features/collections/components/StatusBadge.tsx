import type { CacheStatus } from '@/types/cache';

interface StatusBadgeProps {
  status: CacheStatus;
  showLabel?: boolean;
}

const statusConfig = {
  fresh: {
    color: 'bg-green-500',
    label: 'Fresh',
  },
  stale: {
    color: 'bg-yellow-500',
    label: 'Update Available',
  },
  missing: {
    color: 'bg-red-500',
    label: 'Not Cached',
  },
};

export function StatusBadge({ status, showLabel = false }: StatusBadgeProps) {
  const { color, label } = statusConfig[status];

  return (
    <div className="inline-flex items-center gap-1.5" title={label}>
      <div className={`w-2 h-2 rounded-full ${color}`} />
      {showLabel && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  );
}
