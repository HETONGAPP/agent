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
    <div className="card mb-4 p-4 bg-gray-900/40 border border-gray-800/50">
      <div className="flex flex-col gap-4">
        {/* Use flex layout with wrap, but with fixed min-widths to prevent shifting */}
        <div className="flex items-center gap-3 flex-wrap">
          {children}
        </div>
        {(showClear && onClear) || searchComponent ? (
          <div className="flex items-center justify-between pt-3 border-t border-gray-800/50">
            <div className="flex-1 max-w-md">
              {searchComponent}
            </div>
            {showClear && onClear && (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={onClear}
                className="text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors"
              >
                Clear All Filters
              </Button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};




