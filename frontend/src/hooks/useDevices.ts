/**
 * Custom Hook for Device Management
 * Encapsulates device-related logic
 */

import { useEffect } from 'react';
import { useDeviceStore } from '@/store/useDeviceStore';
import { DeviceFilters } from '@/types';
import { PAGINATION } from '@/config/constants';

export const useDevices = (autoFetch: boolean = true, filters?: DeviceFilters) => {
  const {
    devices,
    selectedDevice,
    stats,
    loading,
    error,
    fetchDevices,
    fetchDevice,
    fetchStats,
    updateStatus,
    removeDevice,
    setFilters,
    setSelectedDevice,
    clearError,
  } = useDeviceStore();

  useEffect(() => {
    if (autoFetch) {
      fetchDevices(filters, PAGINATION.DEFAULT_PAGE_SIZE, 0);
      fetchStats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoFetch, filters]);

  return {
    devices,
    selectedDevice,
    stats,
    loading,
    error,
    fetchDevices,
    fetchDevice,
    fetchStats,
    updateStatus,
    removeDevice,
    setFilters,
    setSelectedDevice,
    clearError,
  };
};

