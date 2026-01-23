/**
 * WebSocket Hook
 * Manages WebSocket connection for real-time updates
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { websocketEventManager } from '@/services/websocketEventManager';

export type EventType = 
  | 'device_status_changed'
  | 'device_added'
  | 'device_removed'
  | 'device_updated'
  | 'alarm_created'
  | 'alarm_updated'
  | 'diagnostic_created'
  | 'stats_updated'
  | 'heartbeat';

// Event type constants for use as values
export const EventType = {
  DEVICE_STATUS_CHANGED: 'device_status_changed' as const,
  DEVICE_ADDED: 'device_added' as const,
  DEVICE_REMOVED: 'device_removed' as const,
  DEVICE_UPDATED: 'device_updated' as const,
  ALARM_CREATED: 'alarm_created' as const,
  ALARM_UPDATED: 'alarm_updated' as const,
  DIAGNOSTIC_CREATED: 'diagnostic_created' as const,
  STATS_UPDATED: 'stats_updated' as const,
  HEARTBEAT: 'heartbeat' as const,
} as const;

export interface WebSocketMessage {
  type: EventType;
  data?: any;
  timestamp?: string;
}

export interface UseWebSocketOptions {
  enabled?: boolean;
  events?: EventType[];
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: any) => void;
}

export interface UseWebSocketReturn {
  connected: boolean;
  error?: any;
}

// Build WebSocket URL from API base URL or use explicit WS URL
const getWebSocketUrl = (): string => {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  
  // Try to derive from API base URL
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  try {
    const url = new URL(apiBaseUrl);
    // Convert http/https to ws/wss
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${url.host}/ws`;
  } catch {
    // Fallback to default
    return `ws://${window.location.hostname}:8000/ws`;
  }
};

const WS_URL = getWebSocketUrl();

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    enabled = true,
    events = [],
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isManuallyDisconnectedRef = useRef(false);
  const pingIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const connectionCheckIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const getReconnectDelay = useCallback((attempt: number): number => {
    const baseDelay = 5000; // 5 seconds
    const maxDelay = 60000; // 60 seconds
    return Math.min(baseDelay * Math.pow(2, Math.min(attempt, 5)), maxDelay);
  }, []);

  const connect = useCallback(() => {
    if (!enabled || isManuallyDisconnectedRef.current) {
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const wsUrl = getWebSocketUrl();
      if (import.meta.env.DEV) {
        console.log(`[useWebSocket] Attempting to connect to: ${wsUrl}`);
      }
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      const connectionTimeout = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          const errorMsg = 'WebSocket connection timeout. Falling back to polling.';
          setError(errorMsg);
          if (import.meta.env.DEV) {
            console.warn(`[useWebSocket] ${errorMsg}`);
          }
          if (onError) {
            onError(errorMsg);
          }
        }
      }, 10000); // 10 seconds timeout

      ws.onopen = () => {
        clearTimeout(connectionTimeout);
        setConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;
        isManuallyDisconnectedRef.current = false;
        if (import.meta.env.DEV) {
          console.log('[useWebSocket] WebSocket connected successfully');
        }

        // Subscribe to events
        if (events.length > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            events: events,
          }));
        }

        // Start ping interval (30 seconds)
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);

        if (onConnect) {
          onConnect();
        }
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          // Handle pong
          if (message.type === 'pong') {
            return;
          }

          // Handle heartbeat
          if (message.type === 'heartbeat') {
            return;
          }

          // Publish to event manager (non-blocking)
          try {
            websocketEventManager.handleMessage(message);
          } catch (err) {
            if (import.meta.env.DEV) {
              console.error('Error in event manager:', err);
            }
          }

          // Also call onMessage callback for backward compatibility
          if (onMessage) {
            try {
              onMessage(message);
            } catch (err) {
              if (import.meta.env.DEV) {
                console.error('Error in onMessage callback:', err);
              }
            }
          }
        } catch (err) {
          if (import.meta.env.DEV) {
            console.error('Error parsing WebSocket message:', err);
          }
        }
      };

      ws.onerror = (event) => {
        clearTimeout(connectionTimeout);
        // Don't set error state immediately - let onclose handle reconnection
        // Only log in development to reduce console spam
        if (import.meta.env.DEV) {
          console.error('[useWebSocket] WebSocket error:', event);
          console.error('[useWebSocket] WebSocket URL:', wsUrl);
          console.error('[useWebSocket] WebSocket readyState:', ws.readyState);
        }
        if (onError) {
          onError(event);
        }
      };

      ws.onclose = (event) => {
        clearTimeout(connectionTimeout);
        setConnected(false);

        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        if (import.meta.env.DEV) {
          console.warn(`[useWebSocket] WebSocket closed. Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`);
          // Code 1006 means abnormal closure (no close frame received)
          // This often happens when connection fails before handshake completes
          if (event.code === 1006) {
            console.warn('[useWebSocket] Abnormal closure - connection may have failed before handshake');
          }
        }

        if (onDisconnect) {
          onDisconnect();
        }

        // Auto-reconnect if not manually disconnected
        if (!isManuallyDisconnectedRef.current && enabled) {
          const delay = getReconnectDelay(reconnectAttemptsRef.current);
          reconnectAttemptsRef.current += 1;
          
          if (import.meta.env.DEV) {
            console.log(`[useWebSocket] Will attempt to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);
          }
          
          // Limit reconnection attempts to avoid spam
          if (reconnectAttemptsRef.current <= 10) {
            reconnectTimeoutRef.current = setTimeout(() => {
              if (!isManuallyDisconnectedRef.current && enabled) {
                connect();
              }
            }, delay);
          } else {
            // After 10 attempts, wait longer before retrying
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current = 0; // Reset after long wait
              if (!isManuallyDisconnectedRef.current && enabled) {
                connect();
              }
            }, 60000); // Wait 1 minute before retrying
          }
        }
      };
    } catch (err) {
      setError(err);
      if (onError) {
        onError(err);
      }
    }
  }, [enabled, events, onMessage, onConnect, onDisconnect, onError, getReconnectDelay]);

  const disconnect = useCallback(() => {
    isManuallyDisconnectedRef.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!enabled) {
      disconnect();
      return;
    }

    // Delay connection slightly to ensure page is fully loaded
    // This helps avoid connection issues during page navigation
    const connectTimeout = setTimeout(() => {
      if (enabled && !isManuallyDisconnectedRef.current) {
        connect();
      }
    }, 100); // 100ms delay

    return () => {
      clearTimeout(connectTimeout);
      disconnect();
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
      if (connectionCheckIntervalRef.current) {
        clearInterval(connectionCheckIntervalRef.current);
      }
    };
  }, [enabled, connect, disconnect]);

  // Reconnect when events change
  useEffect(() => {
    if (connected && wsRef.current?.readyState === WebSocket.OPEN && events.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        events: events,
      }));
    }
  }, [events, connected]);

  return { connected, error };
};
