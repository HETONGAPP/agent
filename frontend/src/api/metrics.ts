/**
 * Metrics API
 * API functions for time series metrics
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
  severity?: string;
  risk_level?: string;
  alarm_type?: string;
  source?: string;
  site_id?: string;
}

export interface TimeSeriesResponse {
  time_series: TimeSeriesDataPoint[];
  total: number;
  interval: string;
  metric_type: string;
}

/**
 * Get time series metrics
 */
export const getTimeSeriesMetrics = async (
  params?: {
    start_time?: string;
    end_time?: string;
    interval?: string; // "1h", "1d", "5m", etc.
    metric_type?: string; // "alarms", "diagnostics", "devices"
    group_by?: string; // "severity", "risk_level", etc.
  }
): Promise<ApiResponse<TimeSeriesResponse>> => {
  const queryParams = new URLSearchParams();
  if (params?.start_time) queryParams.append('start_time', params.start_time);
  if (params?.end_time) queryParams.append('end_time', params.end_time);
  if (params?.interval) queryParams.append('interval', params.interval);
  if (params?.metric_type) queryParams.append('metric_type', params.metric_type);
  if (params?.group_by) queryParams.append('group_by', params.group_by);

  return apiRequest<TimeSeriesResponse>({
    method: 'GET',
    url: `/api/v1/metrics/timeseries?${queryParams.toString()}`,
  });
};

export interface DeviceTimeSeriesDataPoint {
  timestamp: string;
  value: number;
  device_id?: string;
  metric?: string;
  device_type?: string;
  site_id?: string;
}

export interface DeviceTimeSeriesResponse {
  time_series: DeviceTimeSeriesDataPoint[];
  total: number;
  interval: string;
}

/**
 * Get device time series data from MQTT/device_data
 */
export const getDeviceTimeSeries = async (
  params?: {
    device_ids?: string[]; // Array of device IDs
    site_id?: string;
    device_type?: string;
    metric?: string;
    start_time?: string;
    end_time?: string;
    interval?: string; // "5m", "1h", "1d", etc.
    since?: string; // ISO format timestamp for incremental queries (only returns data after this time)
  }
): Promise<ApiResponse<DeviceTimeSeriesResponse>> => {
  const queryParams = new URLSearchParams();
  if (params?.device_ids && params.device_ids.length > 0) {
    queryParams.append('device_ids', params.device_ids.join(','));
  }
  if (params?.site_id) queryParams.append('site_id', params.site_id);
  if (params?.device_type) queryParams.append('device_type', params.device_type);
  if (params?.metric) queryParams.append('metric', params.metric);
  if (params?.start_time) queryParams.append('start_time', params.start_time);
  if (params?.end_time) queryParams.append('end_time', params.end_time);
  if (params?.interval) queryParams.append('interval', params.interval);
  if (params?.since) queryParams.append('since', params.since);

  return apiRequest<DeviceTimeSeriesResponse>({
    method: 'GET',
    url: `/api/v1/metrics/device-timeseries?${queryParams.toString()}`,
  });
};

