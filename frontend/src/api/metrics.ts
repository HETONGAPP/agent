/**
 * Metrics API
 * API functions for system metrics
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

export interface SystemMetrics {
  cpu: {
    usage_percent: number;
    count: number;
    frequency_mhz: number | null;
  };
  memory: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
    usage_percent: number;
  };
  swap: {
    total_gb: number;
    used_gb: number;
    usage_percent: number;
  };
  network: {
    bytes_sent_mb: number;
    bytes_recv_mb: number;
    packets_sent: number;
    packets_recv: number;
  };
  disk_io: {
    read_mb: number;
    write_mb: number;
    read_count: number;
    write_count: number;
  };
}

/**
 * Get system resource metrics (CPU, memory, data throughput)
 */
export const getSystemMetrics = async (): Promise<ApiResponse<SystemMetrics>> => {
  return apiRequest<SystemMetrics>({
    method: 'GET',
    url: '/api/v1/metrics/system',
  });
};

export interface DeviceTimeSeriesDataPoint {
  timestamp: string;
  value: number;
  device_id?: string;
  metric?: string;
}

export interface DeviceTimeSeriesParams {
  device_ids?: string[];
  site_id?: string;
  device_type?: string;
  metric?: string;
  start_time?: string;
  end_time?: string;
  interval?: string;
  since?: string;
}

export interface DeviceTimeSeriesResponse {
  time_series: DeviceTimeSeriesDataPoint[];
  total: number;
  interval: string;
}

/**
 * Get device time series data
 */
export const getDeviceTimeSeries = async (
  params: DeviceTimeSeriesParams
): Promise<ApiResponse<DeviceTimeSeriesResponse>> => {
  const queryParams = new URLSearchParams();
  
  if (params.device_ids && params.device_ids.length > 0) {
    queryParams.append('device_ids', params.device_ids.join(','));
  }
  if (params.site_id) {
    queryParams.append('site_id', params.site_id);
  }
  if (params.device_type) {
    queryParams.append('device_type', params.device_type);
  }
  if (params.metric) {
    queryParams.append('metric', params.metric);
  }
  if (params.start_time) {
    queryParams.append('start_time', params.start_time);
  }
  if (params.end_time) {
    queryParams.append('end_time', params.end_time);
  }
  if (params.interval) {
    queryParams.append('interval', params.interval);
  }
  if (params.since) {
    queryParams.append('since', params.since);
  }
  
  const url = `/api/v1/metrics/device-timeseries${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
  
  return apiRequest<DeviceTimeSeriesResponse>({
    method: 'GET',
    url,
  });
};
