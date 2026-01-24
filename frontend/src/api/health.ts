/**
 * Health Check API
 * API functions for system health monitoring
 */

import { apiRequest } from './client';
import { API_ENDPOINTS } from '@/config/constants';
import { HealthStatus, ApiResponse } from '@/types';

/**
 * Get system health status
 */
export const getHealthStatus = async (): Promise<ApiResponse<HealthStatus>> => {
  return apiRequest<HealthStatus>({
    method: 'GET',
    url: API_ENDPOINTS.HEALTH,
  });
};














