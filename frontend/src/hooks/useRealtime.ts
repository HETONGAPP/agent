/**
 * Real-time Updates Hook
 * Handles real-time data updates using polling with rate limiting
 */

import { useEffect, useRef } from 'react';
import { appConfig } from '@/config/app.config';
import { REFRESH_INTERVALS } from '@/config/constants';

interface UseRealtimeOptions {
  enabled?: boolean;
  interval?: number;
  onUpdate?: () => void;
}

// Global rate limit state to prevent multiple intervals
const globalRateLimit = {
  lastUpdate: 0,
  minInterval: 10000, // Minimum 10 seconds between any updates (reduced for better responsiveness)
  activeIntervals: new Set<string>(), // Track active intervals by page
};

export const useRealtime = ({ enabled = true, interval, onUpdate }: UseRealtimeOptions = {}) => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const onUpdateRef = useRef(onUpdate);
  const intervalIdRef = useRef<string | null>(null);
  const updateInterval = Math.max(interval || REFRESH_INTERVALS.NORMAL, 10000); // Minimum 10 seconds

  // Keep onUpdate ref up to date
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    if (!enabled || !appConfig.features.realTimeUpdates || !onUpdateRef.current) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (intervalIdRef.current) {
        globalRateLimit.activeIntervals.delete(intervalIdRef.current);
        intervalIdRef.current = null;
      }
      return;
    }

    // Generate unique ID for this interval
    const intervalId = `realtime-${Date.now()}-${Math.random()}`;
    intervalIdRef.current = intervalId;

    // Throttled update function
    const throttledUpdate = () => {
      const now = Date.now();
      const timeSinceLastUpdate = now - globalRateLimit.lastUpdate;
      
      if (timeSinceLastUpdate < globalRateLimit.minInterval) {
        // Skip this update if too soon
        return;
      }

      globalRateLimit.lastUpdate = now;
      if (onUpdateRef.current) {
        onUpdateRef.current();
      }
    };

    // Initial update (skip if too soon)
    const now = Date.now();
    if (now - globalRateLimit.lastUpdate >= globalRateLimit.minInterval) {
      throttledUpdate();
    }

    // Set up polling with throttling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    
    globalRateLimit.activeIntervals.add(intervalId);
    intervalRef.current = setInterval(throttledUpdate, updateInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (intervalIdRef.current) {
        globalRateLimit.activeIntervals.delete(intervalIdRef.current);
        intervalIdRef.current = null;
      }
    };
  }, [enabled, updateInterval]);
};

