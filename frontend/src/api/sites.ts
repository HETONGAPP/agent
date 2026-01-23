/**
 * Site Management API
 */

import { apiRequest } from './client';

export interface Site {
  site_id: string;
  site_name: string;
  location?: string;
  country?: string;
  state?: string;
  timezone?: string;
  climate?: string;
  latitude?: number;
  longitude?: number;
  [key: string]: any;
}

export interface SiteStats {
  site_id: string;
  devices: {
    total: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
  };
  alarms: {
    total: number;
    by_severity: Record<string, number>;
  };
}

export interface DeviceRule {
  device_id: string;
  device_type: string;
  device_name: string;
  rules: any[];
  rules_count: number;
}

export interface SiteRules {
  site_id: string;
  rules: any[];
  total: number;
  devices?: DeviceRule[];
  devices_count?: number;
}

export interface SitesResponse {
  status: string;
  data: {
    sites: Site[];
    total: number;
  };
}

export interface SiteResponse {
  status: string;
  data: Site;
}

export interface SiteStatsResponse {
  status: string;
  data: SiteStats;
}

export interface SiteRulesResponse {
  status: string;
  data: SiteRules;
}

/**
 * Get all sites
 */
export const getSites = async (): Promise<SitesResponse> => {
  return apiRequest<SitesResponse>({
    method: 'GET',
    url: '/api/v1/sites',
  });
};

/**
 * Get site by ID
 */
export const getSite = async (siteId: string): Promise<SiteResponse> => {
  return apiRequest<SiteResponse>({
    method: 'GET',
    url: `/api/v1/sites/${siteId}`,
  });
};

/**
 * Get site devices
 */
export const getSiteDevices = async (siteId: string): Promise<any> => {
  return apiRequest({
    method: 'GET',
    url: `/api/v1/sites/${siteId}/devices`,
  });
};

/**
 * Add a device to a site
 */
export const addDeviceToSite = async (siteId: string, deviceData: Partial<Site>): Promise<any> => {
  return apiRequest({
    method: 'POST',
    url: `/api/v1/sites/${siteId}/devices`,
    data: deviceData,
  });
};

/**
 * Get site rules
 */
export const getSiteRules = async (siteId: string): Promise<SiteRulesResponse> => {
  return apiRequest<SiteRulesResponse>({
    method: 'GET',
    url: `/api/v1/sites/${siteId}/rules`,
  });
};

/**
 * Add a rule to a site
 */
export const addSiteRule = async (siteId: string, ruleData: any): Promise<any> => {
  return apiRequest({
    method: 'POST',
    url: `/api/v1/sites/${siteId}/rules`,
    data: ruleData,
  });
};

/**
 * Update a rule in a site
 */
export const updateSiteRule = async (siteId: string, ruleId: string, ruleData: any): Promise<any> => {
  return apiRequest({
    method: 'PUT',
    url: `/api/v1/sites/${siteId}/rules/${ruleId}`,
    data: ruleData,
  });
};

/**
 * Delete a rule from a site
 */
export const deleteSiteRule = async (siteId: string, ruleId: string): Promise<any> => {
  return apiRequest({
    method: 'DELETE',
    url: `/api/v1/sites/${siteId}/rules/${ruleId}`,
  });
};

/**
 * Get site statistics
 */
export const getSiteStats = async (siteId: string): Promise<SiteStatsResponse> => {
  return apiRequest<SiteStatsResponse>({
    method: 'GET',
    url: `/api/v1/sites/${siteId}/stats`,
  });
};

/**
 * Create a new site
 */
export const createSite = async (siteData: Partial<Site>): Promise<SiteResponse> => {
  return apiRequest<SiteResponse>({
    method: 'POST',
    url: '/api/v1/sites',
    data: siteData,
  });
};

/**
 * Reload site configuration
 */
export const reloadSite = async (siteId: string): Promise<any> => {
  return apiRequest({
    method: 'POST',
    url: `/api/v1/sites/${siteId}/reload`,
  });
};

/**
 * Delete a site
 * @param siteId Site ID to delete
 * @param deleteData If true, also delete all historical data (alarms, diagnostics, device data)
 */
export const deleteSite = async (siteId: string, deleteData: boolean = false): Promise<any> => {
  return apiRequest({
    method: 'DELETE',
    url: `/api/v1/sites/${siteId}?delete_data=${deleteData}`,
  });
};

/**
 * Update site configuration
 */
export const updateSite = async (siteId: string, siteData: Partial<Site>): Promise<SiteResponse> => {
  return apiRequest<SiteResponse>({
    method: 'PUT',
    url: `/api/v1/sites/${siteId}`,
    data: siteData,
  });
};

/**
 * Get site alarms
 */
export const getSiteAlarms = async (
  siteId: string,
  filters?: {
    start_time?: string;
    end_time?: string;
    alarm_type?: string;
    severity?: string;
    limit?: number;
  }
): Promise<any> => {
  const params = new URLSearchParams();
  if (filters?.start_time) params.append('start_time', filters.start_time);
  if (filters?.end_time) params.append('end_time', filters.end_time);
  if (filters?.alarm_type) params.append('alarm_type', filters.alarm_type);
  if (filters?.severity) params.append('severity', filters.severity);
  if (filters?.limit) params.append('limit', filters.limit.toString());

  return apiRequest({
    method: 'GET',
    url: `/api/v1/sites/${siteId}/alarms?${params.toString()}`,
  });
};

/**
 * Generate site diagnostic report (manual trigger)
 * Analyzes all devices, alarms, and historical data for comprehensive diagnosis
 */
export const generateSiteDiagnostic = async (
  siteId: string,
  timeRange: string = '-24h'
): Promise<any> => {
  const params = new URLSearchParams();
  if (timeRange) {
    params.append('time_range', timeRange);
  }

  return apiRequest({
    method: 'POST',
    url: `/api/v1/sites/${siteId}/diagnostics/generate?${params.toString()}`,
  });
};

/**
 * Get site diagnostics
 */
export const getSiteDiagnostics = async (
  siteId: string,
  filters?: {
    start_time?: string;
    end_time?: string;
    risk_level?: string;
    limit?: number;
  }
): Promise<any> => {
  const params = new URLSearchParams();
  if (filters?.start_time) params.append('start_time', filters.start_time);
  if (filters?.end_time) params.append('end_time', filters.end_time);
  if (filters?.risk_level) params.append('risk_level', filters.risk_level);
  if (filters?.limit) params.append('limit', filters.limit.toString());

  return apiRequest({
    method: 'GET',
    url: `/api/v1/sites/${siteId}/diagnostics?${params.toString()}`,
  });
};

