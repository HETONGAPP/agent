/**
 * Custom Hook for Diagnostic Management
 * Encapsulates diagnostic-related logic
 */

import { useEffect, useRef } from 'react';
import { useDiagnosticStore } from '@/store/useDiagnosticStore';
import { DiagnosticFilters } from '@/types';

export const useDiagnostics = (autoFetch: boolean = true, filters?: DiagnosticFilters) => {
  const {
    diagnostics,
    selectedDiagnostic,
    stats,
    pagination,
    loading,
    error,
    fetchDiagnostics,
    fetchDiagnostic,
    fetchStats,
    deleteDiagnostic,
    setFilters,
    setPagination,
    setSelectedDiagnostic,
    clearError,
  } = useDiagnosticStore();

  const filtersRef = useRef(filters);
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    if (autoFetch && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchDiagnostics(filtersRef.current, 20, 0);
      fetchStats();
    }
  }, [autoFetch, fetchDiagnostics, fetchStats]);

  return {
    diagnostics,
    selectedDiagnostic,
    stats,
    pagination,
    loading,
    error,
    fetchDiagnostics,
    fetchDiagnostic,
    fetchStats,
    deleteDiagnostic,
    setFilters,
    setPagination,
    setSelectedDiagnostic,
    clearError,
  };
};

