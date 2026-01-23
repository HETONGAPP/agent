/**
 * Export Utility Functions
 * Helper functions for exporting data
 */

import { Device, Alarm, Diagnostic } from '@/types';

/**
 * Export data to CSV format
 */
export const exportToCSV = <T extends Record<string, unknown>>(
  data: T[],
  filename: string,
  headers?: string[]
): void => {
  if (data.length === 0) {
    return;
  }

  // Get headers from first object if not provided
  const csvHeaders = headers || Object.keys(data[0]);
  
  // Create CSV content
  const csvContent = [
    csvHeaders.join(','),
    ...data.map((item) =>
      csvHeaders.map((header) => {
        const value = item[header];
        // Handle values with commas or quotes
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value ?? '';
      }).join(',')
    ),
  ].join('\n');

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', `${filename}.csv`);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * Export data to JSON format
 */
export const exportToJSON = <T>(data: T[], filename: string): void => {
  const jsonContent = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonContent], { type: 'application/json' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', `${filename}.json`);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * Export devices to CSV
 */
export const exportDevices = (devices: Device[]): void => {
  exportToCSV(devices, 'devices', [
    'device_id',
    'device_type',
    'status',
    'integration_name',
    'registered_at',
    'last_seen',
  ]);
};

/**
 * Export alarms to CSV
 */
export const exportAlarms = (alarms: Alarm[]): void => {
  exportToCSV(alarms, 'alarms', [
    'alarm_id',
    'alarm_type',
    'severity',
    'source',
    'timestamp',
  ]);
};

/**
 * Export diagnostics to CSV
 */
export const exportDiagnostics = (diagnostics: Diagnostic[]): void => {
  exportToCSV(diagnostics, 'diagnostics', [
    'alarm_id',
    'risk_level',
    'timestamp',
    'current_status',
  ]);
};












