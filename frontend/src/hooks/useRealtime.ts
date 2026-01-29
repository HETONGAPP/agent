/**
 * Real-time Updates Hook
 * Handles real-time data updates using polling with rate limiting.
 * Pauses polling when tab is hidden (visibility API) to save resources.
 */

import { useEffect, useRef, useState } from 'react';
import { appConfig } from '@/config/app.config';
import { REFRESH_INTERVALS, POLLING_MIN_INTERVAL_MS } from '@/config/constants';

interface UseRealtimeOptions {
  enabled?: boolean;
  interval?: number;
  onUpdate?: () => void;
  /** If true, pause polling when document is hidden (default: true) */
  pauseWhenHidden?: boolean;
}

// Global rate limit state to prevent multiple intervals
const globalRateLimit = {
  lastUpdate: 0,
  minInterval: POLLING_MIN_INTERVAL_MS,
  activeIntervals: new Set<string>(),
};

export const useRealtime = ({
  enabled = true,
  interval,
  onUpdate,
  pauseWhenHidden = true,
}: UseRealtimeOptions = {}) => {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onUpdateRef = useRef(onUpdate);
  const intervalIdRef = useRef<string | null>(null);
  const updateInterval = Math.max(interval ?? REFRESH_INTERVALS.NORMAL, POLLING_MIN_INTERVAL_MS);
  const [isVisible, setIsVisible] = useState(
    () => (typeof document !== 'undefined' ? !document.hidden : true)
  );

  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  // Pause polling when tab is hidden to save CPU and network
  useEffect(() => {
    if (!pauseWhenHidden || typeof document === 'undefined') return;
    const handleVisibility = () => setIsVisible(!document.hidden);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [pauseWhenHidden]);

  useEffect(() => {
    const shouldPoll =
      enabled &&
      appConfig.features.realTimeUpdates &&
      onUpdateRef.current &&
      (!pauseWhenHidden || isVisible);

    if (!shouldPoll) {
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

    const intervalId = `realtime-${Date.now()}-${Math.random()}`;
    intervalIdRef.current = intervalId;

    const throttledUpdate = () => {
      const now = Date.now();
      if (now - globalRateLimit.lastUpdate < globalRateLimit.minInterval) return;
      globalRateLimit.lastUpdate = now;
      onUpdateRef.current?.();
    };

    if (Date.now() - globalRateLimit.lastUpdate >= globalRateLimit.minInterval) {
      throttledUpdate();
    }

    if (intervalRef.current) clearInterval(intervalRef.current);
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
  }, [enabled, updateInterval, pauseWhenHidden, isVisible]);
};

