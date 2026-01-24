/**
 * Date Utility Functions
 * Helper functions for date formatting and manipulation
 */

import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';

/**
 * Format date based on format type
 */
export const formatDate = (
  date: string | Date,
  formatType: 'relative' | 'absolute' | 'iso' = 'relative'
): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    
    if (!isValid(dateObj)) {
      return 'Invalid Date';
    }

    switch (formatType) {
      case 'relative':
        return formatDistanceToNow(dateObj, { addSuffix: true });
      case 'absolute':
        return format(dateObj, 'yyyy-MM-dd HH:mm:ss');
      case 'iso':
        return dateObj.toISOString();
      default:
        return formatDistanceToNow(dateObj, { addSuffix: true });
    }
  } catch (error) {
    return 'Invalid Date';
  }
};

/**
 * Get time range for queries (e.g., last 24 hours)
 */
export const getTimeRange = (hours: number): { start: string; end: string } => {
  const end = new Date();
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000);
  
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
};

/**
 * Format relative time (e.g., "2 hours ago")
 */
export const formatRelativeTime = (date: string | Date): string => {
  return formatDate(date, 'relative');
};

/**
 * Format absolute time (e.g., "2024-01-15 14:30:25")
 */
export const formatAbsoluteTime = (date: string | Date): string => {
  return formatDate(date, 'absolute');
};














