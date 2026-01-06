import { useState } from 'react';
import { Search, Plus } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import * as api from '@/api';
import { MobileMenuButton } from '@/components/layout/MobileMenuButton';
import { ProfileCard } from './ProfileCard';
import { ProfileDetailModal } from './ProfileDetailModal';
import { RegistryManager } from './RegistryManager';
import { ProfileEditorModal } from './ProfileEditorModal';

export function ProfilesPage() {
  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'local' | 'registry'>('all');
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [editingProfile, setEditingProfile] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Filter profiles
  const filteredProfiles = profiles.filter(profile => {
    const matchesSearch = profile.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         profile.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSource = sourceFilter === 'all' || profile.sourceType === sourceFilter;
    return matchesSearch && matchesSource;
  });

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MobileMenuButton />
          <h1 className="text-3xl font-bold">Bundles</h1>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create Bundle
        </button>
      </div>

      {/* Registry Manager */}
      <RegistryManager />

      {/* Filters */}
      <div className="flex items-center gap-2 flex-1">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search bundles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-md"
          />
        </div>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value as 'all' | 'local' | 'registry')}
          className="px-3 py-2 border rounded-md"
        >
          <option value="all">All Sources</option>
          <option value="local">Local Only</option>
          <option value="registry">Registry Only</option>
        </select>
      </div>

      {/* Info about bundle management */}
      <div className="text-sm text-muted-foreground bg-muted/50 p-3 rounded-md">
        <p>Bundles are loaded from <code className="bg-background px-1 rounded">bundles/</code> directory. To create or edit bundles, add/modify <code className="bg-background px-1 rounded">.md</code> files in the bundles directory.</p>
      </div>

      {/* Bundle List */}
      <div className="space-y-2">
        {filteredProfiles.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {searchQuery || sourceFilter !== 'all'
              ? 'No bundles match your filters'
              : 'No bundles found'}
          </div>
        ) : (
          filteredProfiles.map((profile) => (
            <ProfileCard
              key={profile.name}
              profile={profile}
              onView={() => setSelectedProfile(profile.name)}
            />
          ))
        )}
      </div>

      {/* Detail Modal */}
      <ProfileDetailModal
        profileName={selectedProfile}
        onClose={() => setSelectedProfile(null)}
        onEdit={(name) => {
          setSelectedProfile(null);
          setEditingProfile(name);
        }}
      />

      {/* Editor Modal */}
      {(isCreating || editingProfile) && (
        <ProfileEditorModal
          profileName={editingProfile}
          onClose={() => {
            setIsCreating(false);
            setEditingProfile(null);
          }}
        />
      )}
    </div>
  );
}
