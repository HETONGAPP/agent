/**
 * Diagnostic API
 * API functions for diagnostic report management
 */

import { apiRequest } from './client';
import { API_ENDPOINTS } from '@/config/constants';
import { Diagnostic, DiagnosticStats, DiagnosticFilters, ApiResponse } from '@/types';

/**
 * Get list of diagnostic reports with optional filters
 */
export const getDiagnostics = async (
  filters?: DiagnosticFilters,
  limit?: number,
  offset?: number
): Promise<ApiResponse<{ diagnostics: Diagnostic[]; total: number; limit: number; offset: number }>> => {
  const params = new URLSearchParams();
  
  if (filters?.alarm_id) params.append('alarm_id', filters.alarm_id);
  if (filters?.risk_level) params.append('risk_level', filters.risk_level);
  if (filters?.site_id) params.append('site_id', filters.site_id);
  if (filters?.device_type) params.append('device_type', filters.device_type);
  if (filters?.start_time) params.append('start_time', filters.start_time);
  if (filters?.end_time) params.append('end_time', filters.end_time);
  if (limit) params.append('limit', limit.toString());
  if (offset !== undefined) params.append('offset', offset.toString());

  return apiRequest<{ diagnostics: Diagnostic[]; total: number; limit: number; offset: number }>({
    method: 'GET',
    url: `${API_ENDPOINTS.DIAGNOSTICS}?${params.toString()}`,
  });
};

/**
 * Get diagnostic report for a specific alarm
 */
export const getDiagnostic = async (alarmId: string): Promise<ApiResponse<Diagnostic>> => {
  return apiRequest<Diagnostic>({
    method: 'GET',
    url: API_ENDPOINTS.DIAGNOSTIC_DETAIL(alarmId),
  });
};

/**
 * Get diagnostic statistics
 */
export const getDiagnosticStats = async (
  startTime?: string,
  endTime?: string
): Promise<ApiResponse<DiagnosticStats>> => {
  const params = new URLSearchParams();
  if (startTime) params.append('start_time', startTime);
  if (endTime) params.append('end_time', endTime);

  return apiRequest<DiagnosticStats>({
    method: 'GET',
    url: `${API_ENDPOINTS.DIAGNOSTIC_STATS}?${params.toString()}`,
  });
};

/**
 * Get diagnostic report for a specific alarm
 */
export const getDiagnosticByAlarm = async (alarmId: string): Promise<ApiResponse<Diagnostic>> => {
  return apiRequest<Diagnostic>({
    method: 'GET',
    url: `/api/v1/diagnostics/${alarmId}`,
  });
};

/**
 * Generate diagnostic report for a specific alarm (manual trigger)
 */
export const generateAlarmDiagnostic = async (alarmId: string): Promise<ApiResponse<Diagnostic>> => {
  return apiRequest<Diagnostic>({
    method: 'POST',
    url: `/api/v1/alarms/${alarmId}/diagnostic`,
  });
};

/**
 * Delete diagnostic report for a specific alarm
 */
export const deleteDiagnostic = async (alarmId: string): Promise<ApiResponse<void>> => {
  return apiRequest<void>({
    method: 'DELETE',
    url: `/api/v1/diagnostics/${alarmId}`,
  });
};


