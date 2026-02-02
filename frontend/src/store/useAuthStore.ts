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
        console.log('[AuthStore] Logout called');
        set({ isLoading: true });
        try {
          // Call logout endpoint to clear cookie
          // Token is stored in HttpOnly cookie, so we always try to call logout API
          // The backend will clear the cookie even if token is not in state
          console.log('[AuthStore] Calling logout API...');
          try {
            await apiClient.post('/api/auth/logout');
            console.log('[AuthStore] Logout API call successful');
          } catch (error: any) {
            // Ignore 401 errors during logout - this is expected if cookie is already invalid
            // Also ignore other logout errors - still clear local state
            if (error?.response?.status === 401) {
              console.log('[AuthStore] Logout API returned 401 (expected if already logged out)');
            } else {
              console.warn('[AuthStore] Logout API call failed:', error);
            }
          }
        } catch (error) {
          console.error('[AuthStore] Logout error:', error);
        } finally {
          // Cookie will be cleared by backend (or already cleared)
          // Clear local state regardless of API call result
          console.log('[AuthStore] Clearing local auth state');
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
          });
          console.log('[AuthStore] Logout complete');
        }
      },

      fetchUserInfo: async () => {
        // Token is stored in HttpOnly cookie, so we don't check token in state
        // Just try to fetch user info - if cookie exists and is valid, API will return user data
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.get('/api/auth/me');
          set({
            user: response.data,
            token: response.data?.user_id || null, // Store a reference (not the actual token)
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch (error: any) {
          // Cookie might be invalid or expired - clear auth state (expected when not logged in)
          // Do not set error here: "Not authenticated" would show on login page before user does anything
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: null,
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
// Token is stored in HttpOnly cookie, so we try to fetch user info to check authentication
if (typeof window !== 'undefined') {
  // Set initial loading state
  useAuthStore.setState({ isLoading: true });
  
  // Try to fetch user info - if cookie exists and is valid, user will be loaded
  useAuthStore.getState().fetchUserInfo().catch(() => {
    // If fetch fails, user is not authenticated (no valid cookie)
    // This is expected behavior, so we don't need to do anything
    // Loading state will be set to false in fetchUserInfo
  });
}
