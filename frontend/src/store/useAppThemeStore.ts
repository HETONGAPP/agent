/**
 * App Theme Store
 * UI theme: dark, light, or auto (system)
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

export type AppTheme = 'dark' | 'light' | 'auto';

interface AppThemeState {
  theme: AppTheme;
  setTheme: (theme: AppTheme) => void;
  resolvedTheme: () => 'dark' | 'light';
}

const getInitialTheme = (): AppTheme => {
  try {
    const stored = getStorageItem<string>(STORAGE_KEYS.THEME, 'dark');
    return stored === 'light' || stored === 'auto' ? stored : 'dark';
  } catch {
    return 'dark';
  }
};

export const useAppThemeStore = create<AppThemeState>((set, get) => ({
  theme: getInitialTheme(),

  setTheme: (theme: AppTheme) => {
    setStorageItem(STORAGE_KEYS.THEME, theme);
    set({ theme });
  },

  resolvedTheme: () => {
    const { theme } = get();
    if (theme === 'light') return 'light';
    if (theme === 'auto' && typeof window !== 'undefined') {
      return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    return 'dark';
  },
}));
