/**
 * Application Constants
 * Centralized constants to avoid magic numbers and strings
 */

// API Endpoints
export const API_ENDPOINTS = {
  // Health
  HEALTH: '/health',
  
  // Devices
  DEVICES: '/api/v1/devices',
  DEVICE_DETAIL: (id: string) => `/api/v1/devices/${id}`,
  DEVICE_STATUS: (id: string) => `/api/v1/devices/${id}/status`,
  DEVICE_STATS: '/api/v1/devices/stats',
  
  // Alarms
  ALARMS: '/api/v1/alarms',
  ALARM_DETAIL: (id: string) => `/api/v1/alarms/${id}`,
  ALARM_STATS: '/api/v1/alarms/stats',
  
  // Diagnostics
  DIAGNOSTICS: '/api/v1/diagnostics',
  DIAGNOSTIC_DETAIL: (alarmId: string) => `/api/v1/diagnostics/${alarmId}`,
  DIAGNOSTIC_STATS: '/api/v1/diagnostics/stats',
  
  // Integrations
  INTEGRATIONS: '/api/v1/integrations',
  INTEGRATION_REGISTER: '/api/v1/integrations/register',
} as const;

// Device Types
export const DEVICE_TYPES = {
  BMS: 'BMS',
  PCS: 'PCS',
  EMS: 'EMS',
  LOG: 'LOG',
} as const;

export type DeviceType = typeof DEVICE_TYPES[keyof typeof DEVICE_TYPES];

// Device Status
export const DEVICE_STATUS = {
  REGISTERED: 'registered',
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  UNREGISTERED: 'unregistered',
} as const;

export type DeviceStatus = typeof DEVICE_STATUS[keyof typeof DEVICE_STATUS];

// Alarm Severity
export const ALARM_SEVERITY = {
  CRITICAL: 'Critical',
  WARNING: 'Warning',
  INFO: 'Info',
} as const;

export type AlarmSeverity = typeof ALARM_SEVERITY[keyof typeof ALARM_SEVERITY];

// Risk Levels
export const RISK_LEVELS = {
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
} as const;

export type RiskLevel = typeof RISK_LEVELS[keyof typeof RISK_LEVELS];

// Color Mappings
export const SEVERITY_COLORS = {
  [ALARM_SEVERITY.CRITICAL]: 'critical',
  [ALARM_SEVERITY.WARNING]: 'warning',
  [ALARM_SEVERITY.INFO]: 'info',
} as const;

export const RISK_COLORS = {
  [RISK_LEVELS.HIGH]: 'risk-high',
  [RISK_LEVELS.MEDIUM]: 'risk-medium',
  [RISK_LEVELS.LOW]: 'risk-low',
} as const;

export const STATUS_COLORS = {
  [DEVICE_STATUS.ACTIVE]: 'active',
  [DEVICE_STATUS.INACTIVE]: 'inactive',
  [DEVICE_STATUS.REGISTERED]: 'info',
  [DEVICE_STATUS.UNREGISTERED]: 'inactive',
} as const;

// Time Formats
export const TIME_FORMATS = {
  RELATIVE: 'relative',
  ABSOLUTE: 'absolute',
  ISO: 'iso',
} as const;

// Pagination
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
} as const;

// Refresh Intervals (in milliseconds)
export const REFRESH_INTERVALS = {
  REAL_TIME: 5000,      // 5 seconds
  FAST: 10000,          // 10 seconds
  NORMAL: 30000,        // 30 seconds
  SLOW: 60000,          // 1 minute
} as const;

// Local Storage Keys
export const STORAGE_KEYS = {
  THEME: 'bess_theme',
  USER_PREFERENCES: 'bess_user_preferences',
  FLOW_LAYOUT: 'bess_flow_layout',
  SIDEBAR_STATE: 'bess_sidebar_state',
} as const;

