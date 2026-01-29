/**
 * Pagination Component
 * Reusable pagination controls
 */

import { Button } from './Button';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  onItemsPerPageChange?: (itemsPerPage: number) => void;
  itemsPerPageOptions?: number[];
}

export const Pagination = ({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  itemsPerPageOptions = [10, 20, 50, 100],
}: PaginationProps) => {
  // Ensure all values are valid numbers
  const safeCurrentPage = Number.isNaN(currentPage) ? 1 : Math.max(1, currentPage);
  const safeTotalItems = Number.isNaN(totalItems) ? 0 : Math.max(0, totalItems);
  const safeItemsPerPage = Number.isNaN(itemsPerPage) ? 20 : Math.max(1, itemsPerPage);
  const safeTotalPages = Number.isNaN(totalPages) ? 1 : Math.max(1, totalPages);
  
  const startItem = safeTotalItems > 0 ? (safeCurrentPage - 1) * safeItemsPerPage + 1 : 0;
  const endItem = safeTotalItems > 0 ? Math.min(safeCurrentPage * safeItemsPerPage, safeTotalItems) : 0;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-0 mt-4">
      <div className="flex items-center justify-center sm:justify-start gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(safeCurrentPage - 1)}
          disabled={safeCurrentPage === 1}
          className="flex-1 sm:flex-none"
        >
          <span className="text-xs sm:text-sm">Previous</span>
        </Button>
        
        <span className="text-xs sm:text-sm text-gray-300 px-2 sm:px-4 whitespace-nowrap">
          Page {safeCurrentPage} of {safeTotalPages}
        </span>
        
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(safeCurrentPage + 1)}
          disabled={safeCurrentPage === safeTotalPages}
          className="flex-1 sm:flex-none"
        >
          <span className="text-xs sm:text-sm">Next</span>
        </Button>
      </div>
      
      {safeTotalItems > 0 && (
        <div className="text-xs sm:text-sm text-gray-400 text-center sm:text-right">
          Showing {startItem} to {endItem} of {safeTotalItems} items
        </div>
      )}
    </div>
  );
};






