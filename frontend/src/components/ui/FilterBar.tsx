/**
 * Filter Bar Component
 * Reusable filter bar for tables and lists
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
    <div className="card mb-3 sm:mb-4 p-3 sm:p-4 bg-gray-900/40 border border-gray-800/50" style={{ marginLeft: 0, marginRight: 0 }}>
      <div className="flex flex-col gap-3 sm:gap-4">
        {/* Use flex layout with wrap, but with fixed min-widths to prevent shifting */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 flex-wrap">
          {children}
        </div>
        {(showClear && onClear) || searchComponent ? (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 pt-3 border-t border-gray-800/50">
            <div className="flex-1 w-full sm:max-w-md">
              {searchComponent}
            </div>
            {showClear && onClear && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={onClear}
                className="text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors w-full sm:w-auto"
              >
                <span className="text-xs sm:text-sm">Clear All Filters</span>
              </Button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};




