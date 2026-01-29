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

export const useSidebarStore = create<SidebarState>((set, get) => {
  // Initialize mobile menu as closed, especially on mobile devices
  const initialMobileOpen = false;
  if (typeof window !== 'undefined' && window.innerWidth < 1024) {
    console.log('[SidebarStore] Initializing on mobile, ensuring sidebar is closed');
  }
  
  return {
    isCollapsed: getInitialState(),
    isMobileOpen: initialMobileOpen,
    
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
      console.log('[SidebarStore] Opening mobile menu');
      const currentState = get();
      console.log('[SidebarStore] Current state:', currentState);
      set({ isMobileOpen: true });
      const newState = get();
      console.log('[SidebarStore] New state after open:', newState);
    },
    
    closeMobile: () => {
      console.log('[SidebarStore] Closing mobile menu');
      set({ isMobileOpen: false });
    },
  };
});

