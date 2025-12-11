import { useState } from 'react';
import { Plus, Search } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api';
import type { CreateProfileRequest, UpdateProfileRequest, ProfileDetails } from '@/types/api';
import { ProfileCard } from './ProfileCard';
import { ProfileDetailModal } from './ProfileDetailModal';
import { ProfileForm } from './ProfileForm';
import { CopyProfileDialog } from './CopyProfileDialog';
import { RegistryManager } from './RegistryManager';

export function ProfilesPage() {
  const queryClient = useQueryClient();
  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'local' | 'registry'>('all');
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ProfileDetails | null>(null);
  const [copyingProfile, setCopyingProfile] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: api.createProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setIsCreating(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ name, data }: { name: string; data: UpdateProfileRequest }) =>
      api.updateProfile(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      setEditingProfile(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
    },
  });

  const handleEdit = async (profileName: string) => {
    const details = await api.getProfileDetails(profileName);
    if (details.sourceType !== 'local') {
      alert('Only local profiles can be edited');
      return;
    }
    setEditingProfile(details);
  };

  const handleDelete = (profileName: string, sourceType: string) => {
    if (sourceType !== 'local') {
      alert('Only local profiles can be deleted');
      return;
    }
    if (confirm(`Delete profile "${profileName}"?`)) {
      deleteMutation.mutate(profileName);
    }
  };

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
      <div>
        <h1 className="text-3xl font-bold mb-2">Profiles</h1>
        <p className="text-muted-foreground">
          Manage your amplifier profiles and registries
        </p>
      </div>

      {/* Registry Manager */}
      <RegistryManager />

      {/* Filters and Actions */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-1">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search profiles..."
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

        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Create Profile
        </button>
      </div>

      {/* Profile List */}
      <div className="space-y-2">
        {filteredProfiles.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {searchQuery || sourceFilter !== 'all'
              ? 'No profiles match your filters'
              : 'No profiles found'}
          </div>
        ) : (
          filteredProfiles.map((profile) => (
            <ProfileCard
              key={profile.name}
              profile={profile}
              onView={() => setSelectedProfile(profile.name)}
              onEdit={() => handleEdit(profile.name)}
              onDelete={() => handleDelete(profile.name, profile.sourceType)}
              onCopy={() => setCopyingProfile(profile.name)}
            />
          ))
        )}
      </div>

      {/* Modals */}
      <ProfileDetailModal
        profileName={selectedProfile}
        onClose={() => setSelectedProfile(null)}
        onEdit={(profile) => {
          setSelectedProfile(null);
          handleEdit(profile.name);
        }}
        onDelete={(name, sourceType) => {
          setSelectedProfile(null);
          handleDelete(name, sourceType);
        }}
      />

      {isCreating && (
        <ProfileForm
          isOpen={isCreating}
          onClose={() => setIsCreating(false)}
          onSubmit={(data) => createMutation.mutate(data as CreateProfileRequest)}
          mode="create"
        />
      )}

      {editingProfile && (
        <ProfileForm
          isOpen={!!editingProfile}
          onClose={() => setEditingProfile(null)}
          onSubmit={(data) =>
            updateMutation.mutate({
              name: editingProfile.name,
              data: data as UpdateProfileRequest,
            })
          }
          initialData={{
            name: editingProfile.name,
            version: editingProfile.version,
            description: editingProfile.description,
            providers: editingProfile.providers,
            tools: editingProfile.tools,
            hooks: editingProfile.hooks,
            orchestrator: editingProfile.session?.orchestrator,
            context: editingProfile.session?.contextManager,
            agents: editingProfile.agents,
            contexts: editingProfile.contexts,
            instruction: editingProfile.instruction,
          }}
          mode="edit"
        />
      )}

      {copyingProfile && (
        <CopyProfileDialog
          sourceName={copyingProfile}
          onClose={() => setCopyingProfile(null)}
          onSuccess={() => {
            setCopyingProfile(null);
            queryClient.invalidateQueries({ queryKey: ['profiles'] });
          }}
        />
      )}
    </div>
  );
}
