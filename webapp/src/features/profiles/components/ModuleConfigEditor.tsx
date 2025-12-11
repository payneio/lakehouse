import { useState } from 'react';
import { ChevronRight, ChevronDown, Check, X } from 'lucide-react';

interface ModuleConfigEditorProps {
  config?: Record<string, unknown>;
  onChange: (config: Record<string, unknown> | undefined) => void;
  isExpanded: boolean;
  onToggle: () => void;
}

export function ModuleConfigEditor({
  config,
  onChange,
  isExpanded,
  onToggle,
}: ModuleConfigEditorProps) {
  const [editValue, setEditValue] = useState<string>('');
  const [validationError, setValidationError] = useState<string>('');
  const [isEditing, setIsEditing] = useState<boolean>(false);

  const displayValue = isEditing ? editValue : (config ? JSON.stringify(config, null, 2) : '');
  const isValid = !isEditing || !editValue.trim() || !validationError;

  const validateAndUpdate = (value: string) => {
    if (!value.trim()) {
      setValidationError('');
      onChange(undefined);
      return;
    }

    try {
      const parsed = JSON.parse(value);
      setValidationError('');
      onChange(parsed as Record<string, unknown>);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Invalid JSON';
      setValidationError(errorMessage);
    }
  };

  const handleFocus = () => {
    setIsEditing(true);
    setEditValue(config ? JSON.stringify(config, null, 2) : '');
    setValidationError('');
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditValue(e.target.value);
    setValidationError('');
  };

  const handleBlur = () => {
    validateAndUpdate(editValue);
    setIsEditing(false);
  };

  const handleClear = () => {
    setEditValue('');
    setValidationError('');
    setIsEditing(false);
    onChange(undefined);
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        aria-expanded={isExpanded}
        aria-label="Toggle module configuration editor"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <span>Module Configuration</span>
        {config && !isExpanded && (
          <span className="text-xs">(configured)</span>
        )}
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-2">
          <textarea
            value={displayValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder='{"key": "value", "enabled": true}'
            rows={5}
            className="w-full px-3 py-2 border rounded-md text-sm font-mono"
            aria-label="Module configuration JSON"
            aria-describedby="config-validation-status"
          />

          <div className="flex items-center justify-between">
            <div id="config-validation-status" className="flex items-center gap-2 text-sm">
              {!config && !isEditing ? (
                <span className="text-muted-foreground">No configuration</span>
              ) : isValid ? (
                <>
                  <Check className="h-4 w-4 text-green-600" aria-hidden="true" />
                  <span className="text-green-600">Valid JSON</span>
                </>
              ) : (
                <>
                  <X className="h-4 w-4 text-destructive" aria-hidden="true" />
                  <span className="text-destructive">{validationError}</span>
                </>
              )}
            </div>

            {(config || isEditing) && (
              <button
                type="button"
                onClick={handleClear}
                className="text-sm text-muted-foreground hover:text-foreground"
                aria-label="Clear configuration"
              >
                Clear Config
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
