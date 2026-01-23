/**
 * Request Deduplicator
 * Prevents duplicate API requests within a short time window
 */

type RequestKey = string;
type PendingRequest<T> = Promise<T>;

class RequestDeduplicator {
  private pendingRequests = new Map<RequestKey, PendingRequest<any>>();
  private readonly defaultTtl = 100; // 100ms default deduplication window

  /**
   * Execute a request with deduplication
   * If the same request is already pending, returns the existing promise
   */
  async deduplicate<T>(
    key: RequestKey,
    requestFn: () => Promise<T>,
    ttl: number = this.defaultTtl
  ): Promise<T> {
    // Check if request is already pending
    const existing = this.pendingRequests.get(key);
    if (existing) {
      return existing;
    }

    // Create new request
    const promise = requestFn()
      .then((result) => {
        // Remove from pending after a short delay
        setTimeout(() => {
          this.pendingRequests.delete(key);
        }, ttl);
        return result;
      })
      .catch((error) => {
        // Remove immediately on error
        this.pendingRequests.delete(key);
        throw error;
      });

    this.pendingRequests.set(key, promise);
    return promise;
  }

  /**
   * Clear all pending requests
   */
  clear(): void {
    this.pendingRequests.clear();
  }

  /**
   * Get number of pending requests
   */
  getPendingCount(): number {
    return this.pendingRequests.size;
  }
}

// Export singleton instance
export const requestDeduplicator = new RequestDeduplicator();







