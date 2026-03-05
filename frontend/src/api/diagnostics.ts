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
  endTime?: string,
  filters?: DiagnosticFilters
): Promise<ApiResponse<DiagnosticStats>> => {
  const params = new URLSearchParams();
  if (startTime) params.append('start_time', startTime);
  if (endTime) params.append('end_time', endTime);
  if (filters?.site_id) params.append('site_id', filters.site_id);
  if (filters?.risk_level) params.append('risk_level', filters.risk_level);
  if (filters?.device_type) params.append('device_type', filters.device_type);

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
 * Generate diagnostic report for a specific alarm (manual trigger).
 * Optional llm_override is sent when user has set LLM in Settings.
 */
export const generateAlarmDiagnostic = async (
  alarmId: string,
  llmOverride?: { provider?: string; api_key?: string; model?: string; ollama_url?: string; base_url?: string } | null
): Promise<ApiResponse<Diagnostic>> => {
  const body = llmOverride && Object.keys(llmOverride).length > 0 ? { llm_override: llmOverride } : undefined;
  return apiRequest<Diagnostic>({
    method: 'POST',
    url: `/api/v1/alarms/${alarmId}/diagnostic`,
    ...(body && { data: body }),
  });
};

/**
 * Delete diagnostic metadata from PostgreSQL
 */
export const deleteDiagnosticMetadata = async (alarmId: string): Promise<ApiResponse<void>> => {
  return apiRequest<void>({
    method: 'DELETE',
    url: `/api/v1/diagnostics/metadata/${alarmId}`,
  });
};

/**
 * Delete diagnostic report for a specific alarm
 * Also deletes from PostgreSQL metadata if exists
 */
export const deleteDiagnostic = async (alarmId: string): Promise<ApiResponse<void>> => {
  // Delete from InfluxDB (main storage)
  const response = await apiRequest<void>({
    method: 'DELETE',
    url: `/api/v1/diagnostics/${alarmId}`,
  });
  
  // Also try to delete from PostgreSQL metadata (ignore errors if not exists)
  try {
    await deleteDiagnosticMetadata(alarmId);
  } catch (error) {
    // Silently ignore errors - metadata might not exist in PostgreSQL
    console.debug(`Diagnostic metadata not found in PostgreSQL for ${alarmId}, skipping`);
  }
  
  return response;
};

/**
 * Create diagnostic metadata in PostgreSQL
 */
export const createDiagnosticMetadata = async (diagnosticData: {
  alarm_id: string;
  site_id?: string;
  device_id?: string;
  device_type?: string;
  alarm_type?: string;
  risk_level: 'High' | 'Medium' | 'Low';
  current_status?: string;
  diagnostic_name?: string;
  generated_at?: string;
  metadata?: Record<string, any>;
}): Promise<ApiResponse<void>> => {
  return apiRequest<void>({
    method: 'POST',
    url: '/api/v1/diagnostics/metadata',
    data: diagnosticData,
  });
};

/**
 * List diagnostic metadata from PostgreSQL
 */
export const getDiagnosticMetadata = async (
  site_id?: string,
  risk_level?: string,
  limit?: number,
  offset?: number
): Promise<ApiResponse<{ data: Diagnostic[]; total: number }>> => {
  const params = new URLSearchParams();
  if (site_id) params.append('site_id', site_id);
  if (risk_level) params.append('risk_level', risk_level);
  if (limit) params.append('limit', limit.toString());
  if (offset !== undefined) params.append('offset', offset.toString());

  return apiRequest<{ data: Diagnostic[]; total: number }>({
    method: 'GET',
    url: `/api/v1/diagnostics/metadata?${params.toString()}`,
  });
};


