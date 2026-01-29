/**
 * Sidebar Store
 * Zustand store for sidebar collapse state
 */

import { create } from 'zustand';
import { setStorageItem, getStorageItem } from '@/utils/storage';
import { STORAGE_KEYS } from '@/config/constants';

interface SidebarState {
  isCollapsed: boolean;
  isMobileOpen: boolean;
  toggle: () => void;
  setCollapsed: (collapsed: boolean) => void;
  openMobile: () => void;
  closeMobile: () => void;
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
  isMobileOpen: false,
  
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
  
  openMobile: () => {
    set({ isMobileOpen: true });
  },
  
  closeMobile: () => {
    set({ isMobileOpen: false });
  },
}));

