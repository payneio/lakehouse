import React from 'react';
import { X, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExecutionState } from '../types/execution';
import { TurnsList } from './TurnsList';
import { MetricsSummary } from './MetricsSummary';

interface ExecutionPanelProps {
  executionState: ExecutionState;
  isOpen: boolean;
  onClose: () => void;
  onOpen?: () => void;
}

export function ExecutionPanel({ executionState, isOpen, onClose, onOpen }: ExecutionPanelProps) {
  console.log('[ExecutionPanel] Rendering with:', {
    isOpen,
    turnsCount: executionState.turns.length,
    currentTurn: executionState.currentTurn
  });

  const handleOpen = () => {
    console.log('[ExecutionPanel] handleOpen called');
    onOpen?.();
  };

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

      {/* Toggle button when closed */}
      {!isOpen && onOpen && (
        <>
          {/* Desktop: Right edge button */}
          <button
            onClick={(e) => {
              console.log('[ExecutionPanel] Desktop button clicked - opening panel');
              e.stopPropagation();
              handleOpen();
            }}
            className="hidden md:flex fixed right-0 top-1/2 -translate-y-1/2 bg-white border border-border rounded-l-lg px-2 py-4 shadow-md hover:bg-gray-50 transition-colors z-30"
            aria-label="Open execution panel"
          >
            <ChevronRight className="h-5 w-5" />
          </button>

          {/* Mobile: Bottom edge button - positioned above input area */}
          <button
            onClick={(e) => {
              console.log('[ExecutionPanel] Mobile button clicked - opening panel');
              e.stopPropagation();
              handleOpen();
            }}
            className="md:hidden fixed bottom-20 right-4 bg-blue-600 text-white rounded-full px-4 py-2 shadow-lg hover:bg-blue-700 transition-colors z-30 flex items-center gap-2"
            aria-label="Open execution panel"
          >
            <span className="text-sm font-medium">
              Trace ({executionState.turns.length})
            </span>
          </button>
        </>
      )}

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
