import type { Profile } from '@/types/api';

interface ProfileCardProps {
  profile: Profile;
  onView: () => void;
}

export function ProfileCard({ profile, onView }: ProfileCardProps) {
  const isLocal = profile.sourceType === 'local';

  return (
    <div className="border rounded-lg p-4 hover:bg-accent/50 transition-colors cursor-pointer" onClick={onView}>
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
    </div>
  );
}
