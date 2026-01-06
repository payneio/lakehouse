import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import * as api from '@/api';
import type { CreateProfileRequest, UpdateProfileRequest } from '@/types/api';

interface ProfileEditorModalProps {
  profileName?: string | null;
  onClose: () => void;
}

export function ProfileEditorModal({ profileName, onClose }: ProfileEditorModalProps) {
  const queryClient = useQueryClient();
  const isEditing = !!profileName;

  // Fetch existing bundle data if editing
  const { data: existingData } = useQuery({
    queryKey: ['profile-content', profileName],
    queryFn: () => profileName ? api.getProfileContent(profileName) : null,
    enabled: isEditing,
  });

  const [formData, setFormData] = useState<CreateProfileRequest>({
    name: '',
    version: '1.0.0',
    description: '',
    includes: [],
    session: {},
    providers: [],
    tools: [],
    hooks: [],
    agents: {},
    context: {},
    instruction: '',
  });

  // Initialize form data from existing bundle data when editing
  const initialFormData = existingData ? {
    name: existingData.name as string || '',
    version: existingData.version as string || '1.0.0',
    description: existingData.description as string || '',
    includes: (existingData.includes as string[]) || [],
    session: (existingData.session as Record<string, unknown>) || {},
    providers: (existingData.providers as Array<{ module: string; source?: string; config?: Record<string, unknown> }>) || [],
    tools: (existingData.tools as Array<{ module: string; source?: string; config?: Record<string, unknown> }>) || [],
    hooks: (existingData.hooks as Array<{ module: string; source?: string; config?: Record<string, unknown> }>) || [],
    agents: (existingData.agents as Record<string, Record<string, unknown>>) || {},
    context: (existingData.context as Record<string, string>) || {},
    instruction: existingData.instruction as string || '',
  } : formData;

  // Update form data when existing data changes
  useEffect(() => {
    if (existingData && isEditing) {
      setFormData(initialFormData);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing, profileName]);

  const createMutation = useMutation({
    mutationFn: (data: CreateProfileRequest) => api.createProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ name, data }: { name: string; data: UpdateProfileRequest }) =>
      api.updateProfile(name, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] });
      queryClient.invalidateQueries({ queryKey: ['profile-content', profileName] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (isEditing && profileName) {
      const updateData: UpdateProfileRequest = {
        version: formData.version,
        description: formData.description,
        includes: formData.includes,
        session: formData.session,
        providers: formData.providers,
        tools: formData.tools,
        hooks: formData.hooks,
        agents: formData.agents,
        context: formData.context,
        instruction: formData.instruction,
      };
      updateMutation.mutate({ name: profileName, data: updateData });
    } else {
      createMutation.mutate(formData);
    }
  };

  if (!profileName && isEditing) return null;

  const error = createMutation.error || updateMutation.error;
  const isLoading = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-background rounded-lg shadow-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-semibold">
            {isEditing ? `Edit Bundle: ${profileName}` : 'Create New Bundle'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-accent rounded-md transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Basic Info */}
          <div className="space-y-4">
            <h3 className="font-medium text-sm text-muted-foreground">Basic Information</h3>

            <div>
              <label className="block text-sm font-medium mb-1">
                Name {!isEditing && <span className="text-red-500">*</span>}
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={isEditing}
                required={!isEditing}
                className="w-full px-3 py-2 border rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="my-bundle"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Use lowercase letters, numbers, hyphens, and slashes for subdirectories
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Version</label>
              <input
                type="text"
                value={formData.version}
                onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="1.0.0"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border rounded-md"
                rows={2}
                placeholder="Brief description of this bundle"
              />
            </div>
          </div>

          {/* Instruction */}
          <div className="space-y-2">
            <h3 className="font-medium text-sm text-muted-foreground">System Instruction</h3>
            <textarea
              value={formData.instruction}
              onChange={(e) => setFormData({ ...formData, instruction: e.target.value })}
              className="w-full px-3 py-2 border rounded-md font-mono text-sm"
              rows={8}
              placeholder="# System Instruction

You are an AI assistant powered by Amplifier.

@lakehouse:lakehouse.md"
            />
            <p className="text-xs text-muted-foreground">
              Markdown content with optional @mentions for context files
            </p>
          </div>

          {/* Advanced (JSON editors) */}
          <div className="space-y-4">
            <h3 className="font-medium text-sm text-muted-foreground">Advanced Configuration</h3>
            <p className="text-xs text-muted-foreground">
              Edit the raw JSON structure for session, providers, tools, hooks, agents, and context.
              Leave empty for default values.
            </p>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Includes (list of bundle URIs)
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.includes, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, includes: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={4}
                  placeholder='["bundle:foundation/base"]'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Session Config
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.session, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, session: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='{"orchestrator": {"module": "loop-streaming"}}'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Providers
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.providers, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, providers: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='[{"module": "provider-anthropic"}]'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Tools
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.tools, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, tools: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='[{"module": "tool-bash"}]'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Hooks
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.hooks, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, hooks: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='[{"module": "hook-session-start"}]'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Agents
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.agents, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, agents: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='{"agent-name": {"instruction": "..."}}'
                />
              </div>
            </details>

            <details className="border rounded-md">
              <summary className="px-3 py-2 cursor-pointer hover:bg-accent">
                Context Files
              </summary>
              <div className="p-3 border-t">
                <textarea
                  value={JSON.stringify(formData.context, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, context: JSON.parse(e.target.value) });
                    } catch {
                      // Invalid JSON, don't update
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  rows={8}
                  placeholder='{"key": "path/to/file.md"}'
                />
              </div>
            </details>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-md text-sm">
              {error instanceof Error ? error.message : 'An error occurred'}
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border rounded-md hover:bg-accent transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Saving...' : isEditing ? 'Update Bundle' : 'Create Bundle'}
          </button>
        </div>
      </div>
    </div>
  );
}
