/**
 * User menu open state - outside Navbar so opening/closing doesn't re-render the header.
 */

import { create } from 'zustand';

interface UserMenuState {
  open: boolean;
  setOpen: (value: boolean | ((prev: boolean) => boolean)) => void;
}

export const useUserMenuStore = create<UserMenuState>((set) => ({
  open: false,
  setOpen: (value) => set((state) => ({ open: typeof value === 'function' ? value(state.open) : value })),
}));
