import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Trash2 } from 'lucide-react';
import type { CreateProfileRequest, UpdateProfileRequest, ModuleConfig, BehaviorRef, ComponentRefsResponse } from '@/types/api';
import { ComponentSelector } from './ComponentSelector';
import { ModuleConfigEditor } from './ModuleConfigEditor';

interface ProfileFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateProfileRequest | UpdateProfileRequest) => void;
  initialData?: Partial<CreateProfileRequest>;
  mode: 'create' | 'edit';
}

export function ProfileForm({ isOpen, onClose, onSubmit, initialData, mode }: ProfileFormProps) {
  // For now, component refs disabled until we add registry-based component discovery
  const componentRefs = undefined;
  const loadingRefs = false;
  const [showSelector, setShowSelector] = useState<{
    section: 'providers' | 'behaviors' | 'orchestrator' | 'context' | null;
  }>({ section: null });

  const [expandedConfigs, setExpandedConfigs] = useState<{
    providers: Set<number>;
    behaviors: Set<number>;
    orchestrator: boolean;
    context: boolean;
  }>({
    providers: new Set(),
    behaviors: new Set(),
    orchestrator: false,
    context: false,
  });

  const [formData, setFormData] = useState<CreateProfileRequest>({
    name: initialData?.name || '',
    version: initialData?.version || '1.0.0',
    description: initialData?.description || '',
    providers: initialData?.providers || [],
    behaviors: initialData?.behaviors || [],
    orchestrator: initialData?.orchestrator,
    context: initialData?.context,
    instruction: initialData?.instruction || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === 'edit') {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { name, ...updateData } = formData;
      onSubmit(updateData);
    } else {
      onSubmit(formData);
    }
  };

  const addModule = (section: 'providers', uri?: string) => {
    setFormData({
      ...formData,
      [section]: [...(formData[section] || []), { module: '', source: uri || '' }],
    });
  };

  const removeModule = (section: 'providers', index: number) => {
    const updated = [...(formData[section] || [])];
    updated.splice(index, 1);
    setFormData({ ...formData, [section]: updated });
  };

  const updateModule = (
    section: 'providers',
    index: number,
    field: 'module' | 'source' | 'config',
    value: string | Record<string, unknown> | undefined
  ) => {
    const updated = [...(formData[section] || [])];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, [section]: updated });
  };

  const addBehavior = (uri?: string) => {
    setFormData({
      ...formData,
      behaviors: [...(formData.behaviors || []), { id: '', source: uri || '' }],
    });
  };

  const removeBehavior = (index: number) => {
    const updated = [...(formData.behaviors || [])];
    updated.splice(index, 1);
    setFormData({ ...formData, behaviors: updated });
  };

  const updateBehavior = (
    index: number,
    field: 'id' | 'source' | 'config',
    value: string | Record<string, unknown> | undefined
  ) => {
    const updated = [...(formData.behaviors || [])];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, behaviors: updated });
  };

  const toggleBehaviorConfig = (index: number) => {
    setExpandedConfigs(prev => {
      const updated = new Set(prev.behaviors);
      if (updated.has(index)) {
        updated.delete(index);
      } else {
        updated.add(index);
      }
      return { ...prev, behaviors: updated };
    });
  };

  const toggleSingleConfig = (field: 'orchestrator' | 'context') => {
    setExpandedConfigs(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const toggleListConfig = (
    section: 'providers',
    index: number
  ) => {
    setExpandedConfigs(prev => {
      const updated = new Set(prev[section]);
      if (updated.has(index)) {
        updated.delete(index);
      } else {
        updated.add(index);
      }
      return { ...prev, [section]: updated };
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-7xl max-h-[90vh] overflow-y-auto">
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

          {/* Orchestrator */}
          <div className="pt-4 border-t">
            <SingleModuleSection
              title="Orchestrator"
              module={formData.orchestrator}
              onSet={(module) => setFormData({ ...formData, orchestrator: module })}
              onClear={() => setFormData({ ...formData, orchestrator: undefined })}
              isConfigExpanded={expandedConfigs.orchestrator}
              onToggleConfig={() => toggleSingleConfig('orchestrator')}
              showSelector={showSelector}
              setShowSelector={setShowSelector}
              componentRefs={componentRefs}
              loadingRefs={loadingRefs}
            />
          </div>

          {/* Context Manager */}
          <div className="pt-4 border-t">
            <SingleModuleSection
              title="Context Manager"
              module={formData.context}
              onSet={(module) => setFormData({ ...formData, context: module })}
              onClear={() => setFormData({ ...formData, context: undefined })}
              isConfigExpanded={expandedConfigs.context}
              onToggleConfig={() => toggleSingleConfig('context')}
              showSelector={showSelector}
              setShowSelector={setShowSelector}
              componentRefs={componentRefs}
              loadingRefs={loadingRefs}
            />
          </div>

          {/* Providers */}
          <div className="pt-4 border-t">
            <ModuleListSection
              title="Providers"
              modules={formData.providers || []}
              onAdd={(uri) => addModule('providers', uri)}
              onRemove={(i) => removeModule('providers', i)}
              onUpdate={(i, field, value) => updateModule('providers', i, field, value)}
              showSelector={showSelector}
              setShowSelector={setShowSelector}
              componentRefs={componentRefs}
              loadingRefs={loadingRefs}
              expandedConfigs={expandedConfigs.providers}
              onToggleConfig={(i) => toggleListConfig('providers', i)}
            />
          </div>

          {/* Behaviors */}
          <div className="pt-4 border-t">
            <BehaviorListSection
              behaviors={formData.behaviors || []}
              onAdd={(uri) => addBehavior(uri)}
              onRemove={(i) => removeBehavior(i)}
              onUpdate={(i, field, value) => updateBehavior(i, field, value)}
              showSelector={showSelector}
              setShowSelector={setShowSelector}
              componentRefs={componentRefs}
              loadingRefs={loadingRefs}
              expandedConfigs={expandedConfigs.behaviors}
              onToggleConfig={(i) => toggleBehaviorConfig(i)}
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
  onAdd: (uri?: string) => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: 'module' | 'source' | 'config', value: string | Record<string, unknown> | undefined) => void;
  showSelector: { section: 'providers' | 'behaviors' | 'orchestrator' | 'context' | null };
  setShowSelector: (state: { section: 'providers' | 'behaviors' | 'orchestrator' | 'context' | null }) => void;
  componentRefs?: ComponentRefsResponse;
  loadingRefs: boolean;
  expandedConfigs: Set<number>;
  onToggleConfig: (index: number) => void;
}

function ModuleListSection({
  title,
  modules,
  onAdd,
  onRemove,
  onUpdate,
  showSelector,
  setShowSelector,
  componentRefs,
  loadingRefs,
  expandedConfigs,
  onToggleConfig,
}: ModuleListSectionProps) {
  const sectionKey = title.toLowerCase() as 'providers';
  const isShowingSelector = showSelector.section === sectionKey;

  const getComponentsForSection = () => {
    if (!componentRefs) return [];
    if (title === 'Providers') return componentRefs.providers;
    return [];
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium">{title}</label>
        {!isShowingSelector ? (
          <button
            type="button"
            onClick={() => setShowSelector({ section: sectionKey })}
            disabled={loadingRefs}
            className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        ) : (
          <ComponentSelector
            components={getComponentsForSection()}
            onSelect={(uri) => {
              if (uri !== null) {
                onAdd(uri);
              } else {
                onAdd();
              }
              setShowSelector({ section: null });
            }}
            placeholder="Select or add new..."
          />
        )}
      </div>

      <div className="space-y-2">
        {modules.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4 border rounded-md border-dashed">
            No {title.toLowerCase()} configured
          </div>
        ) : (
          modules.map((module, i) => (
            <div key={i} className="border rounded-md p-3">
              <div className="flex gap-2 items-start">
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
              <ModuleConfigEditor
                config={module.config}
                onChange={(config) => onUpdate(i, 'config', config)}
                isExpanded={expandedConfigs.has(i)}
                onToggle={() => onToggleConfig(i)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

interface BehaviorListSectionProps {
  behaviors: BehaviorRef[];
  onAdd: (uri?: string) => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: 'id' | 'source' | 'config', value: string | Record<string, unknown> | undefined) => void;
  showSelector: { section: 'providers' | 'behaviors' | 'orchestrator' | 'context' | null };
  setShowSelector: (state: { section: 'providers' | 'behaviors' | 'orchestrator' | 'context' | null }) => void;
  componentRefs?: ComponentRefsResponse;
  loadingRefs: boolean;
  expandedConfigs: Set<number>;
  onToggleConfig: (index: number) => void;
}

function BehaviorListSection({
  behaviors,
  onAdd,
  onRemove,
  onUpdate,
  showSelector,
  setShowSelector,
  componentRefs,
  loadingRefs,
  expandedConfigs,
  onToggleConfig,
}: BehaviorListSectionProps) {
  const isShowingSelector = showSelector.section === 'behaviors';

  const getComponentsForSection = () => {
    if (!componentRefs) return [];
    return componentRefs.behaviors || [];
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium">Behaviors</label>
        {!isShowingSelector ? (
          <button
            type="button"
            onClick={() => setShowSelector({ section: 'behaviors' })}
            disabled={loadingRefs}
            className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        ) : (
          <ComponentSelector
            components={getComponentsForSection()}
            onSelect={(uri) => {
              if (uri !== null) {
                onAdd(uri);
              } else {
                onAdd();
              }
              setShowSelector({ section: null });
            }}
            placeholder="Select or add new..."
          />
        )}
      </div>

      <div className="space-y-2">
        {behaviors.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4 border rounded-md border-dashed">
            No behaviors configured
          </div>
        ) : (
          behaviors.map((behavior, i) => (
            <div key={i} className="border rounded-md p-3">
              <div className="flex gap-2 items-start">
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={behavior.id}
                    onChange={(e) => onUpdate(i, 'id', e.target.value)}
                    placeholder="Behavior ID"
                    className="px-3 py-2 border rounded-md text-sm"
                    required
                  />
                  <input
                    type="text"
                    value={behavior.source || ''}
                    onChange={(e) => onUpdate(i, 'source', e.target.value)}
                    placeholder="amp://, git+https://, file://..."
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
              <ModuleConfigEditor
                config={behavior.config}
                onChange={(config) => onUpdate(i, 'config', config)}
                isExpanded={expandedConfigs.has(i)}
                onToggle={() => onToggleConfig(i)}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

interface SingleModuleSectionProps {
  title: string;
  module?: ModuleConfig;
  onSet: (module: ModuleConfig) => void;
  onClear: () => void;
  isConfigExpanded: boolean;
  onToggleConfig: () => void;
  showSelector: { section: string | null };
  setShowSelector: (state: { section: string | null }) => void;
  componentRefs?: ComponentRefsResponse;
  loadingRefs: boolean;
}

function SingleModuleSection({
  title,
  module,
  onSet,
  onClear,
  isConfigExpanded,
  onToggleConfig,
  showSelector,
  setShowSelector,
  componentRefs,
  loadingRefs,
}: SingleModuleSectionProps) {
  const sectionKey = title.toLowerCase().replace(' ', '_');
  const isShowingSelector = showSelector.section === sectionKey;

  const getComponentsForSection = () => {
    if (!componentRefs) return [];
    if (title === 'Orchestrator') return componentRefs.orchestrators;
    if (title === 'Context Manager') return componentRefs.contextManagers;
    return [];
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium">{title}</label>
        {!module && !isShowingSelector && (
          <button
            type="button"
            onClick={() => setShowSelector({ section: sectionKey })}
            disabled={loadingRefs}
            className="flex items-center gap-1 text-sm text-primary hover:text-primary/80 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        )}
        {!module && isShowingSelector && (
          <ComponentSelector
            components={getComponentsForSection()}
            onSelect={(uri) => {
              if (uri !== null) {
                onSet({ module: '', source: uri });
              } else {
                onSet({ module: '', source: '' });
              }
              setShowSelector({ section: null });
            }}
            placeholder="Select or add new..."
          />
        )}
      </div>

      {!module ? (
        <div className="text-sm text-muted-foreground text-center py-4 border rounded-md border-dashed">
          Not configured
        </div>
      ) : (
        <div className="border rounded-md p-3">
          <div className="flex gap-2 items-start">
            <div className="flex-1 grid grid-cols-2 gap-2">
              <input
                type="text"
                value={module.module}
                onChange={(e) => onSet({ ...module, module: e.target.value })}
                placeholder="Module name"
                className="px-3 py-2 border rounded-md text-sm"
                required
              />
              <input
                type="text"
                value={module.source || ''}
                onChange={(e) => onSet({ ...module, source: e.target.value })}
                placeholder="git+https://..."
                className="px-3 py-2 border rounded-md text-sm"
              />
            </div>
            <button
              type="button"
              onClick={onClear}
              className="p-2 text-destructive hover:text-destructive/80"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <ModuleConfigEditor
            config={module.config}
            onChange={(config) => onSet({ ...module, config })}
            isExpanded={isConfigExpanded}
            onToggle={onToggleConfig}
          />
        </div>
      )}
    </div>
  );
}
