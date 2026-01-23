/**
 * Data Service
 * Unified data fetching service with request deduplication and caching
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  promise?: Promise<T>;
}

interface RequestOptions {
  cacheTTL?: number; // Cache TTL in milliseconds
  dedupeWindow?: number; // Deduplication window in milliseconds
  forceRefresh?: boolean; // Force refresh, bypass cache
}

class DataService {
  private requestCache = new Map<string, CacheEntry<any>>();
  private pendingRequests = new Map<string, Promise<any>>();
  private defaultCacheTTL = 5000; // 5 seconds default cache
  private defaultDedupeWindow = 1000; // 1 second deduplication window

  /**
   * Generate cache key from request parameters
   */
  private generateCacheKey(method: string, url: string, params?: any): string {
    const paramsStr = params ? JSON.stringify(params) : '';
    return `${method}:${url}:${paramsStr}`;
  }

  /**
   * Clean up expired cache entries
   */
  private cleanupCache(): void {
    const now = Date.now();
    for (const [key, entry] of this.requestCache.entries()) {
      if (now - entry.timestamp > this.defaultCacheTTL * 2) {
        this.requestCache.delete(key);
      }
    }
  }

  /**
   * Fetch data with deduplication and caching
   */
  async fetch<T>(
    method: string,
    url: string,
    params?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    const {
      cacheTTL = this.defaultCacheTTL,
      dedupeWindow = this.defaultDedupeWindow,
      forceRefresh = false,
    } = options;

    const cacheKey = this.generateCacheKey(method, url, params);
    const now = Date.now();

    // Check cache if not forcing refresh and cacheTTL > 0
    if (!forceRefresh && cacheTTL > 0 && this.requestCache.has(cacheKey)) {
      const cached = this.requestCache.get(cacheKey)!;
      const age = now - cached.timestamp;

      // Return cached data if still valid
      if (age < cacheTTL) {
        return cached.data;
      }

      // If cache expired but request is pending, return pending promise
      if (cached.promise && this.pendingRequests.has(cacheKey)) {
        return cached.promise;
      }
    } else if (forceRefresh) {
      // Clear cache for this key when forcing refresh
      this.requestCache.delete(cacheKey);
    }

    // Check if there's a pending request for the same key
    if (this.pendingRequests.has(cacheKey)) {
      const pendingPromise = this.pendingRequests.get(cacheKey)!;
      return pendingPromise;
    }

    // Create new request
    const requestPromise = this.executeRequest<T>(method, url, params).then(
      (data) => {
        // Cache the result only if cacheTTL > 0
        if (cacheTTL > 0) {
          this.requestCache.set(cacheKey, {
            data,
            timestamp: now,
          });
        }

        // Clean up pending request
        this.pendingRequests.delete(cacheKey);

        // Periodic cleanup
        if (Math.random() < 0.1) {
          // 10% chance to cleanup on each request
          this.cleanupCache();
        }

        return data;
      }
    ).catch((error) => {
      // Remove from pending on error
      this.pendingRequests.delete(cacheKey);
      throw error;
    });

    // Store pending request
    this.pendingRequests.set(cacheKey, requestPromise);

    return requestPromise;
  }

  /**
   * Execute the actual HTTP request
   */
  private async executeRequest<T>(
    method: string,
    url: string,
    params?: any
  ): Promise<T> {
    const { apiRequest } = await import('@/api/client');
    
    const requestOptions: any = {
      method: method as any,
      url,
    };

    if (params) {
      if (method === 'GET') {
        const queryParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            queryParams.append(key, String(value));
          }
        });
        requestOptions.url = `${url}?${queryParams.toString()}`;
      } else {
        requestOptions.data = params;
      }
    }

    const response = await apiRequest<T>(requestOptions);
    
    if (response.status === 'success' && response.data !== undefined) {
      return response.data;
    }
    
    throw new Error(response.message || 'Request failed');
  }

  /**
   * Invalidate cache for a specific key pattern
   */
  invalidateCache(pattern?: string): void {
    if (!pattern) {
      // Clear all cache
      this.requestCache.clear();
      return;
    }

    // Clear cache entries matching pattern
    for (const key of this.requestCache.keys()) {
      if (key.includes(pattern)) {
        this.requestCache.delete(key);
      }
    }
  }

  /**
   * Clear all cache and pending requests
   */
  clear(): void {
    this.requestCache.clear();
    this.pendingRequests.clear();
  }

  /**
   * Get cache statistics
   */
  getStats() {
    return {
      cacheSize: this.requestCache.size,
      pendingRequests: this.pendingRequests.size,
    };
  }
}

// Export singleton instance
export const dataService = new DataService();

