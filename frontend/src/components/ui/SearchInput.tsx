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
      className={`w-full px-2.5 py-1.5 text-sm bg-gray-800/80 border border-gray-600/60 rounded text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500/60 focus:border-gray-500 ${className}`}
    />
  );
};






