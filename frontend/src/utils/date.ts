/**
 * Date Utility Functions
 * Helper functions for date formatting and manipulation.
 * Absolute time respects Settings → Timezone.
 */

import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns';
import { useTimezoneStore } from '@/store/useTimezoneStore';
import { usePreferencesStore } from '@/store/usePreferencesStore';

/**
 * Format date based on format type.
 * For 'absolute', uses timezone from useTimezoneStore when not 'local',
 * and time format (24h/12h) from usePreferencesStore.
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
      case 'absolute': {
        const tz = useTimezoneStore.getState().timezone;
        const timeFormat = usePreferencesStore.getState().timeFormat;
        const hour12 = timeFormat === '12h';
        if (tz && tz !== 'local') {
          const s = dateObj.toLocaleString(hour12 ? 'en-US' : 'sv-SE', {
            timeZone: tz,
            hour12,
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          });
          return hour12 ? s : s.replace('T', ' ');
        }
        return hour12
          ? format(dateObj, 'yyyy-MM-dd hh:mm:ss a')
          : format(dateObj, 'yyyy-MM-dd HH:mm:ss');
      }
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














