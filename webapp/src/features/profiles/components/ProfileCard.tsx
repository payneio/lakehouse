import { Edit, Trash2, Copy } from 'lucide-react';
import type { Profile } from '@/types/api';

interface ProfileCardProps {
  profile: Profile;
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onCopy: () => void;
}

export function ProfileCard({ profile, onView, onEdit, onDelete, onCopy }: ProfileCardProps) {
  const isLocal = profile.sourceType === 'local';

  return (
    <div className="border rounded-lg p-4 hover:bg-accent/50 transition-colors">
      <div className="flex items-start justify-between">
        <button
          onClick={onView}
          className="flex-1 text-left"
        >
          <div className="flex items-center gap-2">
            <h3 className="font-medium">{profile.name}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              isLocal
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
            }`}>
              {profile.sourceType}
            </span>
            {profile.isActive && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                active
              </span>
            )}
          </div>
          {profile.description && (
            <p className="text-sm text-muted-foreground mt-1">
              {profile.description}
            </p>
          )}
          {profile.registryId && (
            <p className="text-xs text-muted-foreground mt-1">
              from: {profile.registryId}
            </p>
          )}
        </button>

        <div className="flex gap-1">
          {isLocal && (
            <>
              <button
                onClick={onEdit}
                className="p-1.5 hover:bg-background rounded-md"
                title="Edit profile"
              >
                <Edit className="h-4 w-4" />
              </button>
              <button
                onClick={onDelete}
                className="p-1.5 hover:bg-background rounded-md text-destructive"
                title="Delete profile"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </>
          )}
          <button
            onClick={onCopy}
            className="p-1.5 hover:bg-background rounded-md"
            title="Copy profile"
          >
            <Copy className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
