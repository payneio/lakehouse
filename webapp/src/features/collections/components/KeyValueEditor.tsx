import { Plus, Trash2 } from 'lucide-react';

interface KeyValuePair {
  key: string;
  value: string;
}

interface KeyValueEditorProps {
  label: string;
  items: KeyValuePair[];
  onChange: (items: KeyValuePair[]) => void;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}

export function KeyValueEditor({
  label,
  items,
  onChange,
  keyPlaceholder = 'key',
  valuePlaceholder = 'value',
}: KeyValueEditorProps) {
  const addItem = () => {
    onChange([...items, { key: '', value: '' }]);
  };

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, field: 'key' | 'value', value: string) => {
    const updated = [...items];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium">{label}</label>
        <button
          type="button"
          onClick={addItem}
          className="flex items-center gap-1 text-sm text-primary hover:text-primary/80"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>

      <div className="space-y-2">
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4 border rounded-md border-dashed">
            No {label.toLowerCase()} configured
          </div>
        ) : (
          items.map((item, index) => (
            <div key={index} className="flex gap-2">
              <input
                type="text"
                value={item.key}
                onChange={(e) => updateItem(index, 'key', e.target.value)}
                placeholder={keyPlaceholder}
                className="flex-1 px-3 py-2 border rounded-md text-sm"
              />
              <input
                type="text"
                value={item.value}
                onChange={(e) => updateItem(index, 'value', e.target.value)}
                placeholder={valuePlaceholder}
                className="flex-[2] px-3 py-2 border rounded-md text-sm"
              />
              <button
                type="button"
                onClick={() => removeItem(index)}
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
