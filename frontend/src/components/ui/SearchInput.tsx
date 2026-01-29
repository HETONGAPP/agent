/**
 * Search Input Component
 * Reusable search input with debouncing
 */

import { useState, useEffect, useRef } from 'react';

interface SearchInputProps {
  placeholder?: string;
  onSearch: (query: string) => void;
  debounceMs?: number;
  className?: string;
}

export const SearchInput = ({
  placeholder = 'Search...',
  onSearch,
  debounceMs = 300,
  className = '',
}: SearchInputProps) => {
  const [query, setQuery] = useState('');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Only call onSearch if it's a function
    if (typeof onSearch === 'function') {
      timeoutRef.current = setTimeout(() => {
        onSearch(query);
      }, debounceMs);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [query, onSearch, debounceMs]);

  return (
    <input
      type="text"
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      placeholder={placeholder}
      className={`w-full px-3 sm:px-4 py-2 text-sm sm:text-base bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`}
    />
  );
};






