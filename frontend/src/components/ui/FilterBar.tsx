/**
 * Filter Bar Component
 * Single-row, minimal filter bar for tables and lists
 */

import { ReactNode } from 'react';
import { Button } from './Button';

interface FilterBarProps {
  children: ReactNode;
  onClear?: () => void;
  showClear?: boolean;
  searchComponent?: ReactNode;
}

export const FilterBar = ({ children, onClear, showClear = true, searchComponent }: FilterBarProps) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 sm:p-3.5 rounded-lg bg-gray-800/30 border border-gray-700/50 w-full max-w-full min-w-0">
      {searchComponent && (
        <div className="w-full sm:w-56 shrink-0 min-w-0">
          {searchComponent}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 flex-1 min-w-0 w-full">
        {children}
      </div>
      {showClear && onClear && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          className="shrink-0 text-gray-400 hover:text-white text-xs"
        >
          Clear
        </Button>
      )}
    </div>
  );
};
