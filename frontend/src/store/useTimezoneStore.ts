/**
 * Timezone Store
 * User preference for display timezone (dates/times in the app)
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

export const TIMEZONE_OPTIONS: { value: string; label: string }[] = [
  { value: 'local', label: 'Local (browser)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai' },
  { value: 'Asia/Hong_Kong', label: 'Asia/Hong Kong' },
  { value: 'America/New_York', label: 'America/New York' },
  { value: 'America/Los_Angeles', label: 'America/Los Angeles' },
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'Europe/Paris', label: 'Europe/Paris' },
];

interface TimezoneState {
  timezone: string;
  setTimezone: (timezone: string) => void;
}

const getInitialTimezone = (): string => {
  try {
    const stored = getStorageItem<string>(STORAGE_KEYS.TIMEZONE, 'local');
    return typeof stored === 'string' && stored.length > 0 ? stored : 'local';
  } catch {
    return 'local';
  }
};

export const useTimezoneStore = create<TimezoneState>((set) => ({
  timezone: getInitialTimezone(),

  setTimezone: (timezone: string) => {
    setStorageItem(STORAGE_KEYS.TIMEZONE, timezone);
    set({ timezone });
  },
}));
