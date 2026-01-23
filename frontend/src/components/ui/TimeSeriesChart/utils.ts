/**
 * Time Series Chart Utilities
 * Formatting and helper functions
 */

import { TimeSeriesDataPoint } from './types';

/**
 * Format timestamp for display (time only)
 */
export const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit',
  });
};

/**
 * Format date for display
 */
export const formatDate = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
};

/**
 * Intelligent data sampling to maintain visual quality while reducing points
 * Uses consistent step to prevent visual jumps
 */
export const sampleData = (
  data: TimeSeriesDataPoint[],
  maxPoints: number
): TimeSeriesDataPoint[] => {
  if (data.length <= maxPoints) {
    return data;
  }

  const sampled: TimeSeriesDataPoint[] = [];
  const step = Math.ceil(data.length / maxPoints);
  
  // Always include first point
  sampled.push(data[0]);
  
  // Sample middle points with consistent step
  for (let i = step; i < data.length - step; i += step) {
    sampled.push(data[i]);
  }
  
  // Always include last point
  if (data.length > 1) {
    sampled.push(data[data.length - 1]);
  }
  
  return sampled;
};

/**
 * Validate data point
 */
export const isValidDataPoint = (point: TimeSeriesDataPoint | null | undefined): boolean => {
  if (!point) return false;
  if (!point.timestamp) return false;
  const time = new Date(point.timestamp).getTime();
  if (isNaN(time)) return false;
  if (point.value === null || point.value === undefined) return false;
  if (isNaN(point.value) || !isFinite(point.value)) return false;
  return true;
};

/**
 * Parse timestamp to number
 */
export const parseTimestamp = (timestamp: string): number | null => {
  try {
    const time = new Date(timestamp).getTime();
    return isNaN(time) ? null : time;
  } catch {
    return null;
  }
};








