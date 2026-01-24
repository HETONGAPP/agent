/**
 * Device Store
 * Zustand store for device state management
 */

import { create } from 'zustand';
import { Device, DeviceStats, DeviceFilters } from '@/types';
import { getDevices, getDevice, getDeviceStats, updateDeviceStatus, deleteDevice } from '@/api/devices';

interface DeviceState {
  devices: Device[];
  selectedDevice: Device | null;
  stats: DeviceStats | null;
  filters: DeviceFilters;
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchDevices: (filters?: DeviceFilters, limit?: number, offset?: number, forceUpdate?: boolean) => Promise<void>;
  fetchDevice: (deviceId: string) => Promise<void>;
  fetchStats: () => Promise<void>;
  updateStatus: (deviceId: string, status: string) => Promise<void>;
  removeDevice: (deviceId: string, deleteData?: boolean) => Promise<void>;
  setFilters: (filters: DeviceFilters) => void;
  setSelectedDevice: (device: Device | null) => void;
  clearError: () => void;
}

export const useDeviceStore = create<DeviceState>((set, get) => ({
  devices: [],
  selectedDevice: null,
  stats: null,
  filters: {},
  loading: false,
  error: null,

  fetchDevices: async (filters, limit, offset) => {
    // Only set loading if we don't have devices yet (initial load)
    const currentDevices = get().devices;
    const isInitialLoad = currentDevices.length === 0;
    
    if (isInitialLoad) {
      set({ loading: true, error: null });
    } else {
      // For subsequent updates, don't show loading to avoid flickering
      set({ error: null });
    }
    
    try {
      const response = await getDevices(filters, limit, offset);
      if (response.status === 'success' && response.data) {
        const newDevices = response.data.devices || [];
        console.log('[DeviceStore] Fetched devices:', newDevices.length);
        
        // Only update if data actually changed (compare device IDs, status, and metadata)
        const currentDeviceMap = new Map(currentDevices.map(d => [d.device_id, d]));
        const newDeviceMap = new Map(newDevices.map(d => [d.device_id, d]));
        
        // Check if devices changed (added, removed, status changed, or metadata changed)
        let hasChanges = false;
        if (currentDevices.length !== newDevices.length) {
          hasChanges = true;
        } else {
          for (const device of newDevices) {
            const currentDevice = currentDeviceMap.get(device.device_id);
            if (!currentDevice) {
              hasChanges = true;
              break;
            }
            
            // Check status change
            if (currentDevice.status !== device.status) {
              hasChanges = true;
              break;
            }
            
            // Check integration_name change
            if (currentDevice.integration_name !== device.integration_name) {
              hasChanges = true;
              break;
            }
            
            // Check metadata changes (deep comparison for common fields)
            const currentMetadata = currentDevice.metadata || {};
            const newMetadata = device.metadata || {};
            
            // Compare common metadata fields
            const metadataFields = ['brand', 'model', 'site_id', 'manufacturing_id'];
            for (const field of metadataFields) {
              if (currentMetadata[field] !== newMetadata[field]) {
                hasChanges = true;
                break;
              }
            }
            
            if (hasChanges) {
              break;
            }
          }
        }
        
        // Only update state if there are actual changes
        if (hasChanges || isInitialLoad) {
          set({ devices: newDevices, loading: false });
        } else {
          // No changes, just clear loading state
          set({ loading: false });
        }
      } else {
        console.error('[DeviceStore] Failed to fetch devices:', response.message);
        set({ error: response.message || 'Failed to fetch devices', loading: false, devices: [] });
      }
    } catch (error) {
      console.error('[DeviceStore] Error fetching devices:', error);
      set({ error: 'An error occurred while fetching devices', loading: false, devices: [] });
    }
  },

  fetchDevice: async (deviceId) => {
    set({ loading: true, error: null });
    try {
      const response = await getDevice(deviceId);
      if (response.status === 'success' && response.data) {
        set({ selectedDevice: response.data, loading: false });
      } else {
        set({ error: response.message || 'Failed to fetch device', loading: false });
      }
    } catch (error) {
      set({ error: 'An error occurred while fetching device', loading: false });
    }
  },

  fetchStats: async () => {
    try {
      const response = await getDeviceStats();
      if (response.status === 'success' && response.data) {
        set({ stats: response.data });
      }
    } catch (error: any) {
      // Silently handle request cancellation errors (normal when component unmounts)
      if (error?.message?.includes('aborted') || error?.code === 'ERR_CANCELED' || error?.name === 'AbortError') {
        return; // Silently ignore cancelled requests
      }
      console.error('Failed to fetch device stats:', error);
    }
  },

  updateStatus: async (deviceId, status) => {
    set({ loading: true, error: null });
    try {
      const response = await updateDeviceStatus(deviceId, status);
      if (response.status === 'success' && response.data) {
        // Update device in list
        const devices = get().devices;
        const updatedDevices = devices.map((d) =>
          d.device_id === deviceId ? response.data! : d
        );
        set({ devices: updatedDevices, loading: false });
        
        // Update selected device if it's the one being updated
        const selected = get().selectedDevice;
        if (selected && selected.device_id === deviceId) {
          set({ selectedDevice: response.data });
        }
      } else {
        set({ error: response.message || 'Failed to update device status', loading: false });
      }
    } catch (error) {
      set({ error: 'An error occurred while updating device status', loading: false });
    }
  },

  removeDevice: async (deviceId, deleteData = false) => {
    set({ loading: true, error: null });
    try {
      const response = await deleteDevice(deviceId, deleteData);
      if (response.status === 'success') {
        // Remove device from list
        const devices = get().devices;
        const updatedDevices = devices.filter((d) => d.device_id !== deviceId);
        set({ devices: updatedDevices, loading: false });
        
        // Clear selected device if it's the one being removed
        const selected = get().selectedDevice;
        if (selected && selected.device_id === deviceId) {
          set({ selectedDevice: null });
        }
        
        // Refresh device list to ensure consistency with backend
        const currentFilters = get().filters;
        await get().fetchDevices(currentFilters);
      } else {
        set({ error: response.message || 'Failed to delete device', loading: false });
      }
    } catch (error) {
      set({ error: 'An error occurred while deleting device', loading: false });
    }
  },

  setFilters: (filters) => {
    set({ filters });
  },

  setSelectedDevice: (device) => {
    set({ selectedDevice: device });
  },

  clearError: () => {
    set({ error: null });
  },
}));

