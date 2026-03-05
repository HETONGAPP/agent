/**
 * User Preferences Store
 * Default page size, time format (24h/12h), etc.
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';
import { PAGINATION } from '@/config/constants';

export type TimeFormatPreference = '24h' | '12h';

interface UserPreferences {
  defaultPageSize: number;
  timeFormat: TimeFormatPreference;
}

const defaultPreferences: UserPreferences = {
  defaultPageSize: PAGINATION.DEFAULT_PAGE_SIZE,
  timeFormat: '24h',
};

const getInitialPreferences = (): UserPreferences => {
  try {
    const stored = getStorageItem<Partial<UserPreferences>>(STORAGE_KEYS.USER_PREFERENCES, {});
    const defaultPageSize = PAGINATION.PAGE_SIZE_OPTIONS.includes(Number(stored.defaultPageSize))
      ? Number(stored.defaultPageSize)
      : defaultPreferences.defaultPageSize;
    const timeFormat = stored.timeFormat === '12h' ? '12h' : '24h';
    return { defaultPageSize, timeFormat };
  } catch {
    return defaultPreferences;
  }
};

interface PreferencesState extends UserPreferences {
  setDefaultPageSize: (size: number) => void;
  setTimeFormat: (format: TimeFormatPreference) => void;
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  ...getInitialPreferences(),

  setDefaultPageSize: (defaultPageSize: number) => {
    const prefs = { ...get(), defaultPageSize };
    setStorageItem(STORAGE_KEYS.USER_PREFERENCES, { defaultPageSize: prefs.defaultPageSize, timeFormat: prefs.timeFormat });
    set({ defaultPageSize });
  },

  setTimeFormat: (timeFormat: TimeFormatPreference) => {
    const prefs = { ...get(), timeFormat };
    setStorageItem(STORAGE_KEYS.USER_PREFERENCES, { defaultPageSize: prefs.defaultPageSize, timeFormat: prefs.timeFormat });
    set({ timeFormat });
  },
}));
