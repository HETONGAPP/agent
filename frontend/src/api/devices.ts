/**
 * Device API
 * API functions for device management
 */

import { dataService } from '@/services/dataService';
import { apiRequest } from './client';
import { API_ENDPOINTS } from '@/config/constants';
import { Device, DeviceStats, DeviceFilters, ApiResponse, PaginationInfo } from '@/types';

/**
 * Get list of devices with optional filters
 */
export const getDevices = async (
  filters?: DeviceFilters,
  limit?: number,
  offset?: number
): Promise<ApiResponse<{ devices: Device[]; total: number }>> => {
  const params: any = {};
  
  if (filters?.device_type) params.device_type = filters.device_type;
  if (filters?.status) params.status = filters.status;
  if (filters?.integration_name) params.integration_name = filters.integration_name;
  if (limit) params.limit = limit;
  if (offset) params.offset = offset;

  const url = API_ENDPOINTS.DEVICES;
  const response = await dataService.fetch<{ devices: Device[]; total: number }>(
    'GET',
    url,
    params,
    { cacheTTL: 5000 } // 5 seconds cache
  );

  return {
    status: 'success',
    data: response,
  };
};

/**
 * Get device details by ID
 */
export const getDevice = async (deviceId: string): Promise<ApiResponse<Device>> => {
  return apiRequest<Device>({
    method: 'GET',
    url: API_ENDPOINTS.DEVICE_DETAIL(deviceId),
  });
};

/**
 * Update device status
 */
export const updateDeviceStatus = async (
  deviceId: string,
  status: string
): Promise<ApiResponse<Device>> => {
  return apiRequest<Device>({
    method: 'PUT',
    url: API_ENDPOINTS.DEVICE_STATUS(deviceId),
    data: { status },
  });
};

/**
 * Delete (unregister) device
 * @param deviceId Device ID to delete
 * @param deleteData If true, also delete all historical data (device_data, alarms, diagnostics)
 */
export const deleteDevice = async (deviceId: string, deleteData: boolean = false): Promise<ApiResponse<void>> => {
  return apiRequest<void>({
    method: 'DELETE',
    url: `${API_ENDPOINTS.DEVICE_DETAIL(deviceId)}?delete_data=${deleteData}`,
  });
};

/**
 * Register a new device (frontend-initiated registration)
 */
export const registerDevice = async (deviceData: {
  device_id: string;
  device_type: string;
  integration_name?: string;
  metadata?: Record<string, any>;
}): Promise<ApiResponse<Device>> => {
  return apiRequest<Device>({
    method: 'POST',
    url: API_ENDPOINTS.DEVICES,
    data: deviceData,
  });
};

/**
 * Get device statistics
 */
export const getDeviceStats = async (): Promise<ApiResponse<DeviceStats>> => {
  const response = await dataService.fetch<DeviceStats>(
    'GET',
    API_ENDPOINTS.DEVICE_STATS,
    {},
    { cacheTTL: 10000 } // 10 seconds cache for stats
  );

  return {
    status: 'success',
    data: response,
  };
};

/**
 * Update device information (integration_name, metadata)
 */
export const updateDevice = async (
  deviceId: string,
  deviceData: {
    integration_name?: string;
    metadata?: Record<string, any>;
  }
): Promise<ApiResponse<Device>> => {
  return apiRequest<Device>({
    method: 'PUT',
    url: API_ENDPOINTS.DEVICE_DETAIL(deviceId),
    data: deviceData,
  });
};


