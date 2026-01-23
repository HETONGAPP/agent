/**
 * Toast Store
 * Zustand store for toast notifications
 */

import { create } from 'zustand';
import { ToastType } from '@/components/ui/Toast';

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (messageOrOptions: string | { message: string; type: ToastType }, type?: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
  clearToasts: () => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (messageOrOptions, type?, duration?) => {
    let message: string;
    let toastType: ToastType;
    
    // Support both old format (message, type) and new format ({ message, type })
    if (typeof messageOrOptions === 'string') {
      message = messageOrOptions;
      toastType = type || 'info';
    } else {
      message = messageOrOptions.message;
      toastType = messageOrOptions.type || 'info';
      duration = messageOrOptions.duration;
    }
    
    const id = `toast-${Date.now()}-${Math.random()}`;
    set((state) => ({
      toasts: [...state.toasts, { id, message, type: toastType, duration }],
    }));
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    }));
  },

  clearToasts: () => {
    set({ toasts: [] });
  },
}));




