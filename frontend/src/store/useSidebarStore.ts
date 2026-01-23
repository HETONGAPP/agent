/**
 * Sidebar Store
 * Zustand store for sidebar collapse state
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

interface SidebarState {
  isCollapsed: boolean;
  toggle: () => void;
  setCollapsed: (collapsed: boolean) => void;
}

// Load initial state from localStorage
const getInitialState = (): boolean => {
  try {
    return getStorageItem(STORAGE_KEYS.SIDEBAR_STATE, false);
  } catch {
    return false;
  }
};

export const useSidebarStore = create<SidebarState>((set) => ({
  isCollapsed: getInitialState(),
  
  toggle: () => {
    set((state) => {
      const newState = !state.isCollapsed;
      setStorageItem(STORAGE_KEYS.SIDEBAR_STATE, newState);
      return { isCollapsed: newState };
    });
  },
  
  setCollapsed: (collapsed: boolean) => {
    setStorageItem(STORAGE_KEYS.SIDEBAR_STATE, collapsed);
    set({ isCollapsed: collapsed });
  },
}));

