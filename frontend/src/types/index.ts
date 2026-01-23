/**
 * TypeScript Type Definitions
 * Centralized type definitions for the application
 */

import { DeviceType, DeviceStatus, AlarmSeverity, RiskLevel } from '@/config/constants';

// Device Types
export interface Device extends Record<string, unknown> {
  device_id: string;
  device_type: DeviceType;
  integration_name: string;
  status: DeviceStatus;
  registered_at: string;
  last_seen: string | null;
  metadata: Record<string, unknown>;
}

export interface DeviceStats {
  total: number;
  by_status: Record<DeviceStatus, number>;
  by_type: Record<DeviceType, number>;
  by_integration: Record<string, number>;
}

// Alarm Types
export interface Alarm {
  alarm_id: string;
  alarm_type: string;
  severity: AlarmSeverity;
  timestamp: string;
  source: string;
  site_id?: string;
  alarm_level?: 'system_level' | 'site_level' | 'device_level';
  diagnostic?: Diagnostic;
}

export interface AlarmStats {
  total: number;
  by_severity: Record<AlarmSeverity, number>;
  by_type: Record<string, number>;
  by_source: Record<string, number>;
}

// Diagnostic Types
export interface Diagnostic {
  alarm_id: string;
  risk_level: RiskLevel;
  timestamp: string;
  generated_at?: string;  // ISO format timestamp when diagnostic was generated
  site_id?: string;
  current_status?: string;
  possible_causes?: string[];
  recommended_actions?: string[];
  references?: string[];
  markdown?: string;
}

export interface DiagnosticStats {
  total: number;
  by_risk_level: Record<RiskLevel, number>;
}

// API Response Types
export interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
  pagination?: PaginationInfo;
}

export interface PaginationInfo {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Flow Node Types
export interface FlowNode {
  id: string;
  type: 'device' | 'alarm' | 'diagnostic' | 'rule' | 'action';
  data: NodeData;
  position: { x: number; y: number };
}

export interface NodeData {
  label: string;
  description?: string;
  [key: string]: unknown;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  animated?: boolean;
}

// Filter Types
export interface DeviceFilters {
  device_type?: DeviceType;
  status?: DeviceStatus;
  integration_name?: string;
}

export interface AlarmFilters {
  device_id?: string;
  device_type?: string;
  alarm_type?: string;
  severity?: AlarmSeverity;
  site_id?: string;
  start_time?: string;
  end_time?: string;
}

export interface DiagnosticFilters {
  alarm_id?: string;
  risk_level?: RiskLevel;
  site_id?: string;
  device_type?: string;
  start_time?: string;
  end_time?: string;
}

// Health Check Types
export interface HealthStatus {
  status: 'healthy' | 'degraded';
  version: string;
  services: {
    influxdb?: ServiceStatus;
    mqtt?: ServiceStatus;
    agent?: ServiceStatus;
    collector?: ServiceStatus;
    cache?: CacheStats;
  };
}

export interface ServiceStatus {
  connected?: boolean;
  initialized?: boolean;
  error?: string;
}

export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
  by_risk_level: Record<string, number>;
}

// Site Types
export interface Site {
  site_id: string;
  site_name: string;
  location?: string;
  timezone?: string;
  climate?: string;
  latitude?: number;
  longitude?: number;
  threshold_overrides?: Record<string, any>;
  settings?: Record<string, any>;
  notifications?: Record<string, any>;
  devices?: Record<string, any>;
  [key: string]: any;
}


