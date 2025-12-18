import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExecutionState } from '../types/execution';
import { TurnsList } from './TurnsList';
import { MetricsSummary } from './MetricsSummary';

interface ExecutionPanelProps {
  executionState: ExecutionState;
  isOpen: boolean;
  onClose: () => void;
}

export function ExecutionPanel({ executionState, isOpen, onClose }: ExecutionPanelProps) {
  return (
    <>
      {/* Desktop: Side panel */}
      <div
        className={cn(
          'hidden md:flex fixed right-0 top-0 h-full w-96 bg-white border-l border-border shadow-lg flex-col z-40 transition-transform duration-300',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-lg font-semibold">Execution Trace</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close execution panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <MetricsSummary metrics={executionState.metrics} />
          <TurnsList turns={executionState.turns} />
        </div>
      </div>

      {/* Mobile: Bottom sheet */}
      <div
        className={cn(
          'md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-border shadow-lg flex flex-col z-40 transition-transform duration-300 rounded-t-lg',
          isOpen ? 'translate-y-0' : 'translate-y-full'
        )}
        style={{ maxHeight: '80vh' }}
      >
        {/* Handle for swipe */}
        <div className="flex items-center justify-center py-2">
          <div className="w-12 h-1 bg-gray-300 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <h2 className="text-base font-semibold">Execution Trace</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close execution panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          <MetricsSummary metrics={executionState.metrics} />
          <TurnsList turns={executionState.turns} />
        </div>
      </div>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/20 z-30"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
    </>
  );
}
