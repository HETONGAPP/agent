/**
 * Data Table Component
 * Reusable table component with sorting and filtering
 */

import { ReactNode } from 'react';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState } from './EmptyState';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => ReactNode;
  sortable?: boolean;
  width?: string; // Optional column width (e.g., "150px", "20%")
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
  getRowClassName?: (item: T, index: number) => string;
  highlightedRowKey?: string | null;
  highlightedRowValue?: string | null;
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  loading = false,
  onRowClick,
  emptyMessage = 'No data available',
  getRowClassName,
  highlightedRowKey,
  highlightedRowValue,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="card" style={{ margin: 0 }}>
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="card" style={{ margin: 0 }}>
        <EmptyState
          icon="📭"
          title="No Data"
          description={emptyMessage}
        />
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto scrollbar-thin" style={{ WebkitOverflowScrolling: 'touch' }}>
      <div className="card min-w-full" style={{ margin: 0 }}>
        <table className="w-full table-auto sm:table-fixed" style={{ minWidth: '600px' }}>
          <colgroup>
            {columns.map((column) => (
              <col key={column.key} style={{ width: column.width || 'auto' }} />
            ))}
          </colgroup>
          <thead>
            <tr className="border-b border-gray-700">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className="px-2 sm:px-3 lg:px-4 py-2 sm:py-3 text-left text-xs sm:text-sm font-semibold text-gray-300 whitespace-nowrap"
                  style={{ width: column.width || 'auto' }}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => {
              const isHighlighted = highlightedRowKey && highlightedRowValue && 
                item[highlightedRowKey] === highlightedRowValue;
              const baseClassName = `border-b border-gray-800/50 ${
                onRowClick ? 'cursor-pointer hover:bg-gray-800/50' : ''
              }`;
              const highlightClassName = isHighlighted 
                ? 'bg-amber-500/20 border-amber-500/50 animate-pulse' 
                : '';
              const customClassName = getRowClassName ? getRowClassName(item, index) : '';
              
              // Use a stable key - prefer item.id, item.rule_id, or item.key, fallback to index
              const rowKey = (item as any).id || (item as any).rule_id || (item as any).key || `row-${index}`;
              
              return (
              <tr
                key={rowKey}
                className={`${baseClassName} ${highlightClassName} ${customClassName}`}
              onClick={() => onRowClick?.(item)}
            >
              {columns.map((column) => (
                <td 
                  key={column.key} 
                  className="px-2 sm:px-3 lg:px-4 py-2 sm:py-3 text-xs sm:text-sm text-gray-300"
                  style={{ width: column.width || 'auto' }}
                >
                  <div className="truncate max-w-[150px] sm:max-w-none">
                    {column.render
                      ? column.render(item)
                      : (item[column.key] as ReactNode)}
                  </div>
                </td>
              ))}
            </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}

