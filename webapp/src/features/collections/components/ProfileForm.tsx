import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Trash2 } from 'lucide-react';
import type { CreateProfileRequest, UpdateProfileRequest, ModuleConfig } from '@/types/api';
import { KeyValueEditor } from './KeyValueEditor';

interface ProfileFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateProfileRequest | UpdateProfileRequest) => void;
  initialData?: Partial<CreateProfileRequest>;
  mode: 'create' | 'edit';
}

export function ProfileForm({ isOpen, onClose, onSubmit, initialData, mode }: ProfileFormProps) {
  const [formData, setFormData] = useState<CreateProfileRequest & {
    agentsArray?: { key: string; value: string }[];
    contextsArray?: { key: string; value: string }[];
  }>({
    name: initialData?.name || '',
    version: initialData?.version || '1.0.0',
    description: initialData?.description || '',
    providers: initialData?.providers || [],
    tools: initialData?.tools || [],
    hooks: initialData?.hooks || [],
    orchestrator: initialData?.orchestrator,
    context: initialData?.context,
    agentsArray: initialData?.agents
      ? Object.entries(initialData.agents).map(([key, value]) => ({ key, value }))
      : [],
    contextsArray: initialData?.contexts
      ? Object.entries(initialData.contexts).map(([key, value]) => ({ key, value }))
      : [],
    instruction: initialData?.instruction || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Convert key-value arrays to dicts
    const agents = Object.fromEntries(
      (formData.agentsArray || []).filter(a => a.key && a.value).map(a => [a.key, a.value])
    );

    const contexts = Object.fromEntries(
      (formData.contextsArray || []).filter(c => c.key && c.value).map(c => [c.key, c.value])
    );

    if (mode === 'edit') {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { name, agentsArray, contextsArray, ...updateData } = formData;
      onSubmit({
        ...updateData,
        agents: Object.keys(agents).length > 0 ? agents : undefined,
        contexts: Object.keys(contexts).length > 0 ? contexts : undefined,
      });
    } else {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { agentsArray, contextsArray, ...createData } = formData;
      onSubmit({
        ...createData,
        agents: Object.keys(agents).length > 0 ? agents : undefined,
        contexts: Object.keys(contexts).length > 0 ? contexts : undefined,
      });
    }
  };

  const addModule = (section: 'providers' | 'tools' | 'hooks') => {
    setFormData({
      ...formData,
      [section]: [...(formData[section] || []), { module: '', source: '' }],
    });
  };

  const removeModule = (section: 'providers' | 'tools' | 'hooks', index: number) => {
    const updated = [...(formData[section] || [])];
    updated.splice(index, 1);
    setFormData({ ...formData, [section]: updated });
  };

  const updateModule = (
    section: 'providers' | 'tools' | 'hooks',
    index: number,
    field: 'module' | 'source',
    value: string
  ) => {
    const updated = [...(formData[section] || [])];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, [section]: updated });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{mode === 'create' ? 'Create New Profile' : 'Edit Profile'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Core Information */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                disabled={mode === 'edit'}
                pattern="^[a-z0-9-]+$"
                className="w-full px-3 py-2 border rounded-md disabled:opacity-50"
                required
                placeholder="my-profile"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Lowercase letters, numbers, and hyphens only
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
                className="w-full px-3 py-2 border rounded-md min-h-[80px]"
                placeholder="Profile description..."
              />
            </div>
          </div>

          {/* Providers */}
          <div className="pt-4 border-t">
            <ModuleListSection
              title="Providers"
              modules={formData.providers || []}
              onAdd={() => addModule('providers')}
              onRemove={(i) => removeModule('providers', i)}
              onUpdate={(i, field, value) => updateModule('providers', i, field, value)}
            />
          </div>

          {/* Tools */}
          <div className="pt-4 border-t">
            <ModuleListSection
              title="Tools"
              modules={formData.tools || []}
              onAdd={() => addModule('tools')}
              onRemove={(i) => removeModule('tools', i)}
              onUpdate={(i, field, value) => updateModule('tools', i, field, value)}
            />
          </div>

          {/* Hooks */}
          <div className="pt-4 border-t">
            <ModuleListSection
              title="Hooks"
              modules={formData.hooks || []}
              onAdd={() => addModule('hooks')}
              onRemove={(i) => removeModule('hooks', i)}
              onUpdate={(i, field, value) => updateModule('hooks', i, field, value)}
            />
          </div>

          {/* Agents */}
          <div className="pt-4 border-t">
            <KeyValueEditor
              label="Agents"
              items={formData.agentsArray || []}
              onChange={(items) => setFormData({ ...formData, agentsArray: items })}
              keyPlaceholder="agent-name"
              valuePlaceholder="@agents/agent.md or https://..."
            />
          </div>

          {/* Contexts */}
          <div className="pt-4 border-t">
            <KeyValueEditor
              label="Contexts"
              items={formData.contextsArray || []}
              onChange={(items) => setFormData({ ...formData, contextsArray: items })}
              keyPlaceholder="context-name"
              valuePlaceholder="@contexts/dir or git+https://..."
            />
          </div>

          {/* System Instruction */}
          <div className="pt-4 border-t">
            <label className="block text-sm font-medium mb-2">System Instruction</label>
            <textarea
              value={formData.instruction || ''}
              onChange={(e) => setFormData({ ...formData, instruction: e.target.value })}
              rows={10}
              placeholder="Additional markdown content for the profile..."
              className="w-full px-3 py-2 border rounded-md font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">
              This content appears in the profile markdown file after the frontmatter
            </p>
          </div>

          {/* Footer */}
          <div className="flex gap-2 justify-end pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border rounded-md hover:bg-accent"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              {mode === 'create' ? 'Create Profile' : 'Save Changes'}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface ModuleListSectionProps {
  title: string;
  modules: ModuleConfig[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: 'module' | 'source', value: string) => void;
}

function ModuleListSection({ title, modules, onAdd, onRemove, onUpdate }: ModuleListSectionProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium">{title}</label>
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center gap-1 text-sm text-primary hover:text-primary/80"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>

      <div className="space-y-2">
        {modules.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4 border rounded-md border-dashed">
            No {title.toLowerCase()} configured
          </div>
        ) : (
          modules.map((module, i) => (
            <div key={i} className="flex gap-2 items-start">
              <div className="flex-1 grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={module.module}
                  onChange={(e) => onUpdate(i, 'module', e.target.value)}
                  placeholder="Module name"
                  className="px-3 py-2 border rounded-md text-sm"
                  required
                />
                <input
                  type="text"
                  value={module.source || ''}
                  onChange={(e) => onUpdate(i, 'source', e.target.value)}
                  placeholder="git+https://..."
                  className="px-3 py-2 border rounded-md text-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => onRemove(i)}
                className="p-2 text-destructive hover:text-destructive/80"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
