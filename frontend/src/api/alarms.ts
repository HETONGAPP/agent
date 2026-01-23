/**
 * Alarm API
 * API functions for alarm management
 */

import { dataService } from '@/services/dataService';
import { API_ENDPOINTS } from '@/config/constants';
import { Alarm, AlarmStats, AlarmFilters, ApiResponse } from '@/types';
import { apiRequest } from './client';

/**
 * Get list of alarms with optional filters and pagination
 */
export const getAlarms = async (
  filters?: AlarmFilters,
  limit?: number,
  offset?: number,
  aggregateBySite?: boolean
): Promise<ApiResponse<{ alarms: Alarm[] | any[]; total: number; limit: number; offset: number }>> => {
  const params: any = {};
  
  if (filters?.device_id) params.device_id = filters.device_id;
  if (filters?.device_type) params.device_type = filters.device_type;
  if (filters?.alarm_type) params.alarm_type = filters.alarm_type;
  if (filters?.severity) params.severity = filters.severity;
  if (filters?.site_id) params.site_id = filters.site_id;
  if (filters?.start_time) params.start_time = filters.start_time;
  if (filters?.end_time) params.end_time = filters.end_time;
  if (limit) params.limit = limit;
  if (offset) params.offset = offset;
  if (aggregateBySite) params.aggregate_by_site = 'true';

  const url = API_ENDPOINTS.ALARMS;
  // Disable cache for site summary views to ensure fresh data and prevent duplicate issues
  // Use forceRefresh to bypass cache for aggregateBySite requests
  const response = await dataService.fetch<{ alarms: Alarm[]; total: number; limit: number; offset: number }>(
    'GET',
    url,
    params,
    { 
      cacheTTL: aggregateBySite ? 0 : 5000, // No cache for site summary, 5 seconds for details
      forceRefresh: aggregateBySite // Force refresh for site summary to avoid stale data
    }
  );

  return {
    status: 'success',
    data: response,
  };
};

/**
 * Get alarm details by ID
 */
export const getAlarm = async (alarmId: string): Promise<ApiResponse<Alarm>> => {
  return apiRequest<Alarm>({
    method: 'GET',
    url: API_ENDPOINTS.ALARM_DETAIL(alarmId),
  });
};

/**
 * Get alarm statistics
 */
export const getAlarmStats = async (
  startTime?: string,
  endTime?: string
): Promise<ApiResponse<AlarmStats>> => {
  const params: any = {};
  if (startTime) params.start_time = startTime;
  if (endTime) params.end_time = endTime;

  const url = API_ENDPOINTS.ALARM_STATS;
  const response = await dataService.fetch<AlarmStats>(
    'GET',
    url,
    params,
    { cacheTTL: 10000 } // 10 seconds cache for stats
  );

  return {
    status: 'success',
    data: response,
  };
};




