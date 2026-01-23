/**
 * API Client
 * Centralized HTTP client for API requests with rate limiting and retry logic
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { appConfig } from '@/config/app.config';
import { ApiResponse } from '@/types';

// Request deduplication map
const pendingRequests = new Map<string, Promise<any>>();

// Rate limit state
let rateLimitUntil = 0;
let consecutive429Errors = 0;

/**
 * Create request key for deduplication
 */
const getRequestKey = (config: AxiosRequestConfig): string => {
  return `${config.method?.toUpperCase()}_${config.url}_${JSON.stringify(config.params || {})}`;
};

/**
 * Create axios instance with default configuration
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: appConfig.api.baseUrl,
    timeout: appConfig.api.timeout,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor
  client.interceptors.request.use(
    async (config) => {
      // Check if we're rate limited - reject immediately to prevent queue buildup
      const now = Date.now();
      if (now < rateLimitUntil) {
        const waitTime = Math.ceil((rateLimitUntil - now) / 1000);
        const error = new Error(`Rate limited. Please wait ${waitTime}s before retrying.`);
        (error as any).response = { status: 429 };
        (error as any).isRateLimit = true;
        return Promise.reject(error);
      }

      // Add auth token if available
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor
  client.interceptors.response.use(
    (response) => {
      // Reset rate limit state on success
      consecutive429Errors = 0;
      rateLimitUntil = 0;
      return response;
    },
    async (error: AxiosError) => {
      // Handle rate limiting (429)
      if (error.response?.status === 429) {
        consecutive429Errors++;
        
        // Get retry-after header or use exponential backoff
        const retryAfter = error.response.headers['retry-after'];
        const waitTime = retryAfter 
          ? parseInt(retryAfter) * 1000 
          : Math.min(1000 * Math.pow(2, consecutive429Errors - 1), 120000); // Max 120s
        
        rateLimitUntil = Date.now() + waitTime;
        
        console.warn(`Rate limit exceeded. Blocking requests for ${Math.ceil(waitTime / 1000)}s...`);
        
        // Don't retry automatically - reject immediately to prevent more requests
        return Promise.reject(error);
      }

      // Reset on other errors
      if (error.response?.status !== 429) {
        consecutive429Errors = 0;
        rateLimitUntil = 0;
      }

      // Handle other common errors
      if (error.response) {
        switch (error.response.status) {
          case 401:
            console.error('Unauthorized access');
            break;
          case 403:
            console.error('Forbidden access');
            break;
          case 404:
            console.error('Resource not found');
            break;
          case 500:
            console.error('Server error');
            break;
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
};

export const apiClient = createApiClient();

/**
 * Generic API request wrapper with deduplication and retry logic
 */
export const apiRequest = async <T>(
  config: AxiosRequestConfig,
  retryOn429: boolean = false
): Promise<ApiResponse<T>> => {
  const requestKey = getRequestKey(config);
  
  // Check for duplicate pending request
  if (pendingRequests.has(requestKey)) {
    try {
      return await pendingRequests.get(requestKey)!;
    } catch (error) {
      // If the pending request failed, continue with new request
    }
  }

  const makeRequest = async (): Promise<ApiResponse<T>> => {
    try {
      const response = await apiClient.request<ApiResponse<T>>(config);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        // Retry on 429 if enabled
        if (error.response?.status === 429 && retryOn429) {
          const retryAfter = error.response.headers['retry-after'];
          const waitTime = retryAfter 
            ? parseInt(retryAfter) * 1000 
            : 5000; // Default 5s
          
          await new Promise(resolve => setTimeout(resolve, waitTime));
          
          // Retry once
          try {
            const retryResponse = await apiClient.request<ApiResponse<T>>(config);
            return retryResponse.data;
          } catch (retryError) {
            // If retry also fails, return error
          }
        }

        return {
          status: 'error',
          message: error.response?.data?.detail || error.message || 'An error occurred',
        };
      }
      return {
        status: 'error',
        message: 'Unknown error occurred',
      };
    } finally {
      // Remove from pending requests
      pendingRequests.delete(requestKey);
    }
  };

  // Store pending request
  const requestPromise = makeRequest();
  pendingRequests.set(requestKey, requestPromise);

  return requestPromise;
};

