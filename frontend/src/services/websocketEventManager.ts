/**
 * WebSocket Event Manager
 * Unified event management using publish-subscribe pattern
 */

import { EventType, WebSocketMessage } from '@/hooks/useWebSocket';

type EventHandler = (data: any) => void | Promise<void>;

class WebSocketEventManager {
  private subscribers = new Map<EventType, Set<EventHandler>>();
  private eventQueue: WebSocketMessage[] = [];
  private isProcessingQueue = false;

  /**
   * Subscribe to an event type
   */
  subscribe(eventType: EventType, handler: EventHandler): () => void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }

    this.subscribers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.subscribers.get(eventType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.subscribers.delete(eventType);
        }
      }
    };
  }

  /**
   * Unsubscribe from an event type
   */
  unsubscribe(eventType: EventType, handler: EventHandler): void {
    const handlers = this.subscribers.get(eventType);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscribers.delete(eventType);
      }
    }
  }

  /**
   * Publish an event to all subscribers
   */
  async publish(eventType: EventType, data: any): Promise<void> {
    const handlers = this.subscribers.get(eventType);
    if (!handlers || handlers.size === 0) {
      return;
    }

    // Execute all handlers
    const promises: Promise<void>[] = [];
    for (const handler of handlers) {
      try {
        const result = handler(data);
        if (result instanceof Promise) {
          promises.push(result);
        }
      } catch (error) {
        console.error(`Error in event handler for ${eventType}:`, error);
      }
    }

    // Wait for all handlers to complete
    await Promise.allSettled(promises);
  }

  /**
   * Handle WebSocket message and publish to subscribers
   */
  async handleMessage(message: WebSocketMessage): Promise<void> {
    // Add to queue for processing
    this.eventQueue.push(message);

    // Process queue if not already processing
    if (!this.isProcessingQueue) {
      this.processQueue();
    }
  }

  /**
   * Process event queue
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessingQueue || this.eventQueue.length === 0) {
      return;
    }

    this.isProcessingQueue = true;

    while (this.eventQueue.length > 0) {
      const message = this.eventQueue.shift();
      if (message) {
        await this.publish(message.type, message.data);
      }
    }

    this.isProcessingQueue = false;
  }

  /**
   * Clear all subscribers
   */
  clear(): void {
    this.subscribers.clear();
    this.eventQueue = [];
  }

  /**
   * Get subscription statistics
   */
  getStats() {
    const stats: Record<string, number> = {};
    for (const [eventType, handlers] of this.subscribers.entries()) {
      stats[eventType] = handlers.size;
    }
    return {
      totalSubscriptions: Array.from(this.subscribers.values()).reduce(
        (sum, handlers) => sum + handlers.size,
        0
      ),
      byEventType: stats,
      queueLength: this.eventQueue.length,
    };
  }
}

// Export singleton instance
export const websocketEventManager = new WebSocketEventManager();









