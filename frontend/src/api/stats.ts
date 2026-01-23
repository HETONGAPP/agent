/**
 * System Statistics API
 * API functions for system-wide statistics
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

export interface SystemStats {
  devices: {
    total: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
  };
  alarms: {
    total: number;
    by_severity: Record<string, number>;
  };
  diagnostics: {
    total: number;
    by_risk_level: Record<string, number>;
  };
  sites: {
    total: number;
  };
}

/**
 * Get system-wide statistics
 */
export const getSystemStats = async (): Promise<ApiResponse<SystemStats>> => {
  return apiRequest<SystemStats>({
    method: 'GET',
    url: '/api/v1/stats',
  });
};











