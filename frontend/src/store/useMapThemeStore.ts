/**
 * Map Theme Store
 * User preference for map tile style: dark or light
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

export type MapTheme = 'dark' | 'light';

interface MapThemeState {
  mapTheme: MapTheme;
  setMapTheme: (theme: MapTheme) => void;
}

const getInitialTheme = (): MapTheme => {
  try {
    const stored = getStorageItem<string>(STORAGE_KEYS.MAP_THEME, 'dark');
    return stored === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
};

export const useMapThemeStore = create<MapThemeState>((set) => ({
  mapTheme: getInitialTheme(),

  setMapTheme: (theme: MapTheme) => {
    setStorageItem(STORAGE_KEYS.MAP_THEME, theme);
    set({ mapTheme: theme });
  },
}));
