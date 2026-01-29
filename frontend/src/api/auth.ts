/**
 * Authentication API
 * API functions for user authentication
 */

import { apiRequest } from './client';
import { ApiResponse } from '@/types';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  verification_code: string;
  full_name?: string;
}

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

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

/**
 * Login user
 */
export const login = async (data: LoginRequest): Promise<ApiResponse<TokenResponse>> => {
  return apiRequest<TokenResponse>({
    method: 'POST',
    url: '/api/auth/login',
    data,
  });
};

/**
 * Register new user
 */
export const register = async (data: RegisterRequest): Promise<ApiResponse<TokenResponse>> => {
  return apiRequest<TokenResponse>({
    method: 'POST',
    url: '/api/auth/register',
    data,
  });
};

/**
 * Logout user
 */
export const logout = async (): Promise<ApiResponse<{ message: string }>> => {
  return apiRequest<{ message: string }>({
    method: 'POST',
    url: '/api/auth/logout',
  });
};

/**
 * Get current user info
 */
export const getCurrentUser = async (): Promise<ApiResponse<User>> => {
  return apiRequest<User>({
    method: 'GET',
    url: '/api/auth/me',
  });
};

/**
 * Send verification code to email
 */
export const sendVerificationCode = async (email: string): Promise<ApiResponse<{ message: string; email: string; verification_code?: string }>> => {
  try {
    return await apiRequest<{ message: string; email: string; verification_code?: string }>({
      method: 'POST',
      url: '/api/auth/send-verification-code',
      data: { email },
    });
  } catch (error: any) {
    // In dev mode, error response might contain verification_code (even for 429 or other errors)
    if (error.response?.data?.verification_code) {
      return {
        status: 'success',
        data: {
          message: error.response.data.message || error.response.data.detail || 'Verification code generated (dev mode)',
          email: email,
          verification_code: error.response.data.verification_code,
        },
      };
    }
    throw error;
  }
};

/**
 * Verify email verification code
 */
export const verifyCode = async (email: string, code: string): Promise<ApiResponse<{ message: string; email: string; verified: boolean }>> => {
  return apiRequest<{ message: string; email: string; verified: boolean }>({
    method: 'POST',
    url: '/api/auth/verify-code',
    data: { email, verification_code: code },
  });
};
