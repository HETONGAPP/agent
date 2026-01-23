/**
 * Custom Hook for Alarm Management
 * Encapsulates alarm-related logic
 */

import { useEffect, useRef } from 'react';
import { useAlarmStore } from '@/store/useAlarmStore';
import { AlarmFilters } from '@/types';

export const useAlarms = (autoFetch: boolean = true, filters?: AlarmFilters) => {
  const {
    alarms,
    selectedAlarm,
    stats,
    pagination,
    loading,
    error,
    fetchAlarms,
    fetchAlarm,
    fetchStats,
    setFilters,
    setPagination,
    setSelectedAlarm,
    clearError,
  } = useAlarmStore();

  const hasFetchedRef = useRef(false);

  // Don't auto-fetch - let components control when to fetch
  // This prevents conflicts between different fetch calls
  useEffect(() => {
    if (autoFetch && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      // Skip auto-fetch to avoid conflicts
      // Components should explicitly call fetchAlarms with correct parameters
    }
  }, [autoFetch]);

  return {
    alarms,
    selectedAlarm,
    stats,
    pagination,
    loading,
    error,
    fetchAlarms,
    fetchAlarm,
    fetchStats,
    setFilters,
    setPagination,
    setSelectedAlarm,
    clearError,
  };
};

