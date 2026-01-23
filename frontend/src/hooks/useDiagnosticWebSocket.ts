/**
 * Diagnostic WebSocket Hook
 * Manages WebSocket connection for diagnostic agent real-time updates
 */

import { useEffect, useRef, useCallback } from 'react';
import { useDiagnosticAgentStore } from '../store/useDiagnosticAgentStore';

interface UseDiagnosticWebSocketOptions {
  siteId: string | null;
  enabled?: boolean;
  baseUrl?: string;
}

export function useDiagnosticWebSocket({
  siteId,
  enabled = true,
  baseUrl = '',
}: UseDiagnosticWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const {
    setTasks,
    updateTask,
    updateAgentStatus,
    addMessage,
    completeDiagnostic,
  } = useDiagnosticAgentStore();

  const connect = useCallback(() => {
    if (!siteId || !enabled) {
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = `${baseUrl.replace(/^http/, 'ws')}/ws/diagnostics/${siteId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('Diagnostic WebSocket connected');
      reconnectAttempts.current = 0;
      addMessage({
        type: 'success',
        content: 'Connected to diagnostic service',
      });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('Diagnostic WebSocket error:', error);
      addMessage({
        type: 'error',
        content: 'WebSocket connection error',
      });
    };

    ws.onclose = () => {
      console.log('Diagnostic WebSocket disconnected');
      wsRef.current = null;

      // Attempt to reconnect
      if (enabled && reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 30000);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };

    wsRef.current = ws;
  }, [siteId, enabled, baseUrl, addMessage]);

  const handleWebSocketMessage = useCallback(
    (data: any) => {
      const { type, data: eventData } = data;

      switch (type) {
        case 'connected':
          addMessage({
            type: 'success',
            content: eventData.message || 'Connected',
          });
          break;

        case 'diagnostic_task_created':
          if (eventData.tasks) {
            setTasks(eventData.tasks);
            addMessage({
              type: 'info',
              content: `Created ${eventData.tasks.length} diagnostic tasks`,
            });
          }
          break;

        case 'diagnostic_task_updated':
          if (eventData.task_id) {
            updateTask(eventData.task_id, {
              status: eventData.status,
              started_at: eventData.started_at,
              completed_at: eventData.completed_at,
              error: eventData.error,
            });
          }
          break;

        case 'diagnostic_agent_status':
          if (eventData.agent) {
            updateAgentStatus(
              eventData.agent,
              eventData.status,
              eventData.task_id,
              eventData.error
            );
          }
          break;

        case 'diagnostic_message':
          addMessage({
            type: eventData.level || 'info',
            content: eventData.message,
            agent: eventData.agent,
          });
          break;

        case 'diagnostic_complete':
          completeDiagnostic(eventData.final_result);
          addMessage({
            type: 'success',
            content: 'Diagnostic completed',
          });
          break;

        case 'error':
          addMessage({
            type: 'error',
            content: eventData.message || 'Unknown error',
          });
          break;

        default:
          console.log('Unknown WebSocket message type:', type);
      }
    },
    [setTasks, updateTask, updateAgentStatus, addMessage, completeDiagnostic]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (enabled && siteId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, siteId, connect, disconnect]);

  return {
    connect,
    disconnect,
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  };
}

