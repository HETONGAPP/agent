/**
 * Authentication Store
 * Manages user authentication state using Zustand
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { apiClient } from '@/api/client';

export interface User {
  user_id: string;
  username: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  last_login?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, verificationCode: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  fetchUserInfo: () => Promise<void>;
  clearError: () => void;
  setToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      setToken: (token: string) => {
        // Token is now stored in HttpOnly cookie by backend
        // We still store it in state for reference, but not in localStorage
        set({ token, isAuthenticated: true });
      },

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.post('/api/auth/login', {
            username,
            password,
          });

          const { access_token, user } = response.data;
          
          // Token is stored in HttpOnly cookie by backend
          // Store token in state for reference only
          set({
            user,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || error.message || 'Login failed';
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });
          throw new Error(errorMessage);
        }
      },

      register: async (username: string, email: string, password: string, verificationCode: string, fullName?: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.post('/api/auth/register', {
            username,
            email,
            password,
            verification_code: verificationCode,
            full_name: fullName,
          });

          const { access_token, user } = response.data;
          
          // Token is stored in HttpOnly cookie by backend
          // Store token in state for reference only
          set({
            user,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || error.message || '注册失败';
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });
          throw new Error(errorMessage);
        }
      },

      logout: async () => {
        set({ isLoading: true });
        try {
          // Call logout endpoint if authenticated
          const { token } = get();
          if (token) {
            try {
              await apiClient.post('/api/auth/logout');
            } catch (error) {
              // Ignore logout errors - still clear local state
              console.warn('Logout API call failed:', error);
            }
          }
        } catch (error) {
          console.error('Logout error:', error);
        } finally {
          // Cookie will be cleared by backend
          // Clear local state regardless of API call result
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          });
        }
      },

      fetchUserInfo: async () => {
        const { token } = get();
        if (!token) {
          set({ isAuthenticated: false, user: null });
          return;
        }

        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.get('/api/auth/me');
          set({
            user: response.data,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          // Token might be invalid - clear auth state
          // Cookie will be handled by backend
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: error.response?.data?.detail || 'Failed to fetch user information',
          });
        }
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // Don't persist token in localStorage - it's in HttpOnly cookie
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Initialize auth state on app start
// Token is stored in HttpOnly cookie, so we just try to fetch user info
if (typeof window !== 'undefined') {
  // Try to fetch user info - if cookie exists and is valid, user will be loaded
  useAuthStore.getState().fetchUserInfo().catch(() => {
    // If fetch fails, user is not authenticated (no valid cookie)
    // This is expected behavior, so we don't need to do anything
  });
}
