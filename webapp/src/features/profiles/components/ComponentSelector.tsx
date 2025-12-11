import { Plus } from 'lucide-react';
import type { ComponentRef } from '@/types/api';

interface ComponentSelectorProps {
  components: ComponentRef[];
  onSelect: (uri: string | null) => void;
  placeholder?: string;
}

export function ComponentSelector({ components, onSelect, placeholder }: ComponentSelectorProps) {
  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === '') return; // Placeholder selected
    if (value === 'other') {
      onSelect(null); // null means "Other (blank)"
    } else {
      onSelect(value);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <select
        onChange={handleSelect}
        className="flex-1 px-3 py-2 border rounded-md text-sm bg-background"
        defaultValue=""
        size={1}
      >
        <option value="" disabled>
          {placeholder || 'Select component...'}
        </option>
        <option value="other">Other (blank) - Add new component</option>
        <optgroup label="Existing Components">
          {components.map((component, idx) => (
            <option key={`${component.profile}-${component.uri}-${idx}`} value={component.uri}>
              {component.profile}/{component.name}: {component.uri}
            </option>
          ))}
        </optgroup>
      </select>
      <Plus className="h-4 w-4 text-muted-foreground" />
    </div>
  );
}
