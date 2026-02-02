/**
 * Dashboard Page
 * Main overview page with statistics and recent activity
 */

import { useEffect, useCallback, useState } from 'react';
import { Chart } from '@/components/ui/Chart';
import { PageLoading } from '@/components/ui/PageLoading';
import { useDevices } from '@/hooks/useDevices';
import { useAlarms } from '@/hooks/useAlarms';
import { useDiagnostics } from '@/hooks/useDiagnostics';
import { useRealtime } from '@/hooks/useRealtime';
import { useWebSocket, type EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { formatNumber } from '@/utils/format';
import { Plug, Bell, FileText, AlertTriangle, Cpu, HardDrive, Network, Cloud } from 'lucide-react';
import { getSystemMetrics, type SystemMetrics } from '@/api/metrics';
import { getWeather, type WeatherData } from '@/api/weather';
import { REFRESH_INTERVALS } from '@/config/constants';

export const Dashboard = () => {
  const { stats: deviceStats, fetchStats: fetchDeviceStats } = useDevices(false);
  const { stats: alarmStats, fetchStats: fetchAlarmStats } = useAlarms(false);
  const { stats: diagnosticStats, fetchStats: fetchDiagnosticStats, diagnostics, fetchDiagnostics, loading: loadingDiagnostics } = useDiagnostics(false);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loadingWeather, setLoadingWeather] = useState(false);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  const fetchSystemMetrics = useCallback(async () => {
    setLoadingMetrics(true);
    try {
      const response = await getSystemMetrics();
      if (response.status === 'success' && response.data) {
        setSystemMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch system metrics:', error);
    } finally {
      setLoadingMetrics(false);
    }
  }, []);

  // Get user location
  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          console.log('User location detected:', { lat, lng });
          setUserLocation({ lat, lng });
        },
        (error) => {
          console.warn('Failed to get user location:', error);
          // Don't set default location - let user know location is needed
          console.warn('Location permission denied or unavailable. Weather will not be displayed.');
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0, // Always get fresh location
        }
      );
    } else {
      console.warn('Geolocation is not supported by this browser.');
    }
  }, []);

  const fetchWeather = useCallback(async () => {
    if (!userLocation) return;
    
    setLoadingWeather(true);
    try {
      const response = await getWeather(userLocation.lat, userLocation.lng);
      if (response.status === 'success' && response.data) {
        setWeather(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch weather:', error);
    } finally {
      setLoadingWeather(false);
    }
  }, [userLocation]);

  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      try {
        await Promise.all([
          fetchDeviceStats(),
          fetchAlarmStats(),
          fetchDiagnosticStats(),
          fetchDiagnostics(undefined, 1000, 0),
          fetchSystemMetrics(),
        ]);
      } finally {
        setInitialLoading(false);
      }
    };
    loadInitialData();
    // Weather will be fetched when userLocation is available
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only execute once on component mount

  // Fetch weather when user location is available
  useEffect(() => {
    if (userLocation) {
      fetchWeather();
    }
  }, [userLocation, fetchWeather]);

  // WebSocket for real-time updates
  const wsEvents: EventType[] = [
    'device_added',
    'device_removed',
    'device_updated',
    'device_status_changed',
    'alarm_created',
    'alarm_updated',
    'stats_updated',
    'diagnostic_created',
  ];
  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents,
    onMessage: useCallback((message: { type: EventType; data?: any }) => {
      // Refresh stats when any relevant event occurs
      const shouldRefresh = 
        message.type === 'device_added' ||
        message.type === 'device_removed' ||
        message.type === 'device_updated' ||
        message.type === 'device_status_changed' ||
        message.type === 'alarm_created' ||
        message.type === 'alarm_updated' ||
        message.type === 'stats_updated' ||
        message.type === 'diagnostic_created';
      
      if (shouldRefresh) {
        // For diagnostic_created, refresh list immediately (no delay needed for list)
        if (message.type === 'diagnostic_created') {
          // Refresh diagnostics list immediately for real-time distribution
          fetchDiagnostics(undefined, 1000, 0);
          // Stats can wait a bit for backend processing
          setTimeout(() => {
            fetchDiagnosticStats(undefined, undefined, undefined, true);
          }, 1000);
        } else if (message.type === 'stats_updated') {
          // Force update diagnostic stats to bypass cache
          setTimeout(() => {
            fetchDiagnosticStats(undefined, undefined, undefined, true);
            fetchDiagnostics(undefined, 1000, 0);
          }, 1000);
        } else {
          fetchDiagnosticStats();
        }
        fetchAlarmStats();
        fetchDeviceStats();
      }
    }, [fetchAlarmStats, fetchDiagnosticStats, fetchDeviceStats, fetchDiagnostics]),
    onConnect: useCallback(() => {
      fetchDeviceStats();
      fetchAlarmStats();
      fetchDiagnosticStats();
      fetchDiagnostics(undefined, 1000, 0);
    }, [fetchDeviceStats, fetchAlarmStats, fetchDiagnosticStats, fetchDiagnostics]),
  });

  // Subscribe to WebSocket events via event manager for real-time updates
  useEffect(() => {
    if (!connected) return;

    // Debounce timer for stats refresh
    let statsRefreshTimer: ReturnType<typeof setTimeout> | null = null;
    
    const debouncedRefreshStats = () => {
      if (statsRefreshTimer) {
        clearTimeout(statsRefreshTimer);
      }
      // Add delay to ensure backend has processed the update
      statsRefreshTimer = setTimeout(() => {
        // Force update to bypass any client-side caching
        fetchDiagnosticStats(undefined, undefined, undefined, true);
        fetchAlarmStats();
        fetchDeviceStats();
        fetchDiagnostics(undefined, 1000, 0);
      }, 1000); // 1 second delay to ensure backend processing is complete
    };

    const refreshAllStats = () => {
      fetchDiagnosticStats(undefined, undefined, undefined, true);
      fetchAlarmStats();
      fetchDeviceStats();
      fetchDiagnostics(undefined, 1000, 0);
    };

    const unsubscribeDeviceAdded = websocketEventManager.subscribe('device_added', debouncedRefreshStats);
    const unsubscribeDeviceRemoved = websocketEventManager.subscribe('device_removed', debouncedRefreshStats);
    const unsubscribeDeviceUpdated = websocketEventManager.subscribe('device_updated', debouncedRefreshStats);
    const unsubscribeDeviceStatusChanged = websocketEventManager.subscribe('device_status_changed', debouncedRefreshStats);
    const unsubscribeAlarmCreated = websocketEventManager.subscribe('alarm_created', debouncedRefreshStats);
    const unsubscribeAlarmUpdated = websocketEventManager.subscribe('alarm_updated', debouncedRefreshStats);
    const unsubscribeDiagnosticCreated = websocketEventManager.subscribe('diagnostic_created', (data) => {
      console.log('[Dashboard] Diagnostic created, refreshing stats:', data);
      // Refresh diagnostics list immediately for real-time distribution (no delay for list)
      // This ensures the list is updated as soon as possible
      fetchDiagnostics(undefined, 1000, 0);
      // Also refresh stats with delay to ensure backend processing is complete
      debouncedRefreshStats();
    });
    const unsubscribeStatsUpdated = websocketEventManager.subscribe('stats_updated', () => {
      console.log('[Dashboard] Stats updated, refreshing stats');
      refreshAllStats();
    });

    return () => {
      if (statsRefreshTimer) {
        clearTimeout(statsRefreshTimer);
      }
      unsubscribeDeviceAdded();
      unsubscribeDeviceRemoved();
      unsubscribeDeviceUpdated();
      unsubscribeDeviceStatusChanged();
      unsubscribeAlarmCreated();
      unsubscribeAlarmUpdated();
      unsubscribeDiagnosticCreated();
      unsubscribeStatsUpdated();
    };
  }, [connected, fetchDiagnosticStats, fetchAlarmStats, fetchDeviceStats, fetchDiagnostics]);

  // Fallback polling (only when WebSocket is not connected)
  useRealtime({
    enabled: !connected,
    interval: REFRESH_INTERVALS.DASHBOARD_FALLBACK,
    onUpdate: () => {
      fetchDeviceStats();
      fetchAlarmStats();
      fetchDiagnosticStats();
      fetchDiagnostics(undefined, 1000, 0);
    },
  });

  // Backup polling for diagnostics list (even when WebSocket connected)
  useRealtime({
    enabled: true,
    interval: REFRESH_INTERVALS.DASHBOARD_DIAG_LIST,
    onUpdate: () => {
      if (!loadingDiagnostics) {
        fetchDiagnostics(undefined, 1000, 0, true);
      }
    },
  });

  // System metrics update
  useRealtime({
    enabled: true,
    interval: REFRESH_INTERVALS.FAST,
    onUpdate: () => {
      fetchSystemMetrics();
    },
  });

  // Weather update (30 minutes)
  useRealtime({
    enabled: true,
    interval: 30 * 60 * 1000,
    onUpdate: () => {
      fetchWeather();
    },
  });

  // Prepare chart data
  const alarmChartData = alarmStats
    ? Object.entries(alarmStats.by_severity || {}).map(([label, value]) => ({
        label,
        value: value as number,
        color:
          label === 'Critical'
            ? '#EF4444'
            : label === 'Warning'
            ? '#F59E0B'
            : '#3B82F6',
      }))
    : [];

  // Calculate risk level distribution from diagnostics list (real-time, no cache)
  const diagnosticChartData = (() => {
    if (!diagnostics || diagnostics.length === 0) {
      // Fallback to stats if diagnostics list is not available yet
      if (diagnosticStats?.by_risk_level) {
        const byRiskLevel = diagnosticStats.by_risk_level || {};
        const normalized: Record<string, number> = {};
        Object.entries(byRiskLevel).forEach(([key, value]) => {
          const normalizedKey = key.charAt(0).toUpperCase() + key.slice(1).toLowerCase();
          normalized[normalizedKey] = (normalized[normalizedKey] || 0) + (value as number);
        });
        return Object.entries(normalized).map(([label, value]) => ({
          label,
          value: value as number,
          color:
            label === 'High'
              ? '#DC2626'
              : label === 'Medium'
              ? '#EA580C'
              : '#16A34A',
        }));
      }
      return [];
    }
    
    // Calculate distribution from diagnostics list
    const riskLevelCounts: Record<string, number> = {};
    diagnostics.forEach((diagnostic) => {
      const riskLevel = diagnostic?.risk_level || (diagnostic as any)?.risk_level || 'Unknown';
      const normalizedKey = String(riskLevel).charAt(0).toUpperCase() + String(riskLevel).slice(1).toLowerCase();
      riskLevelCounts[normalizedKey] = (riskLevelCounts[normalizedKey] || 0) + 1;
    });
    
    // Map to chart data with consistent labels and colors
    return Object.entries(riskLevelCounts).map(([label, value]) => ({
      label,
      value: value as number,
      color:
        label === 'High'
          ? '#DC2626'
          : label === 'Medium'
          ? '#EA580C'
          : '#16A34A',
    }));
  })();

  // Show loading state during initial data fetch
  // This must be after all hooks to comply with Rules of Hooks
  if (initialLoading) {
    return <PageLoading message="Loading dashboard..." />;
  }

  return (
    <div className="space-y-6 sm:space-y-8 lg:space-y-10 w-full min-w-0 max-w-full" style={{ boxSizing: 'border-box' }}>
      {/* Hero header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-5">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-blue-400/90 mb-2">
            System overview and statistics
          </p>
          <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            <span className="bg-gradient-to-r from-white via-gray-100 to-gray-300 bg-clip-text text-transparent">
              Dashboard
            </span>
          </h1>
          <div className="mt-3 h-px w-20 sm:w-24 bg-gradient-to-r from-blue-500/80 via-blue-400/50 to-transparent rounded-full" aria-hidden />
        </div>
        {/* Weather Widget */}
        {!userLocation ? (
          <div className="flex items-center gap-2 text-gray-500 text-xs sm:text-sm">
            <Cloud size={14} className="sm:w-4 sm:h-4 shrink-0" />
            <span className="hidden sm:inline">Location permission needed for weather</span>
            <span className="sm:hidden">Location needed</span>
          </div>
        ) : loadingWeather ? (
          <div className="flex items-center gap-2 text-gray-500">
            <Cloud size={18} className="sm:w-5 sm:h-5 shrink-0" />
            <span className="text-xs sm:text-sm">Loading...</span>
          </div>
        ) : weather ? (
          <div className="flex items-center gap-2 sm:gap-3 rounded-2xl px-4 sm:px-5 py-3 border border-white/10 bg-white/5 backdrop-blur-md shrink-0 sm:shadow-lg sm:shadow-black/10">
            <div className="flex items-center gap-3">
              {weather.icon && (
                <img
                  src={`https://openweathermap.org/img/wn/${weather.icon}@2x.png`}
                  alt={weather.description}
                  className="w-9 h-9 sm:w-11 sm:h-11 shrink-0"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
              <div className="flex flex-col min-w-0">
                <span className="text-xl sm:text-2xl font-bold text-white tabular-nums">{weather.temperature}°C</span>
                <span className="text-xs text-gray-400 truncate">{weather.city}{weather.country && `, ${weather.country}`}</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Overview stats */}
      <section>
        <p className="text-xs font-medium uppercase tracking-[0.15em] text-gray-400 mb-4">Overview</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-blue-500/30 sm:hover:shadow-blue-500/5 transition-all duration-300">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" aria-hidden />
          <div className="relative flex flex-col gap-4">
            <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-500/20 text-blue-400 sm:shadow-lg sm:shadow-blue-500/10" aria-hidden>
              <Plug size={24} strokeWidth={1.5} />
            </span>
            <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
              {formatNumber(deviceStats?.total || 0)}
            </p>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Total Devices</p>
          </div>
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-amber-500/30 sm:hover:shadow-amber-500/5 transition-all duration-300">
          <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" aria-hidden />
          <div className="relative flex flex-col gap-4">
            <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-amber-500/20 text-amber-400 sm:shadow-lg sm:shadow-amber-500/10" aria-hidden>
              <Bell size={24} strokeWidth={1.5} />
            </span>
            <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
              {formatNumber(alarmStats?.total || 0)}
            </p>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Active Alarms</p>
          </div>
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-violet-500/30 sm:hover:shadow-violet-500/5 transition-all duration-300">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" aria-hidden />
          <div className="relative flex flex-col gap-4">
            <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-violet-500/20 text-violet-400 sm:shadow-lg sm:shadow-violet-500/10" aria-hidden>
              <FileText size={24} strokeWidth={1.5} />
            </span>
            <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
              {formatNumber(diagnostics?.length || diagnosticStats?.total || 0)}
            </p>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Diagnostic Reports</p>
          </div>
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-red-500/30 sm:hover:shadow-red-500/5 transition-all duration-300">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" aria-hidden />
          <div className="relative flex flex-col gap-4">
            <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-red-500/20 text-red-400 sm:shadow-lg sm:shadow-red-500/10" aria-hidden>
              <AlertTriangle size={24} strokeWidth={1.5} />
            </span>
            <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
              {formatNumber(alarmStats?.by_severity?.Critical || 0)}
            </p>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Critical Alarms</p>
          </div>
        </div>
        </div>
      </section>

      {/* Distributions */}
      <section>
        <p className="text-xs font-medium uppercase tracking-[0.15em] text-gray-400 mb-4">Distributions</p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6 lg:gap-8">
        {/* Alarm Distribution */}
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
          <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" aria-hidden />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-amber-400/90 mb-1">By severity</p>
              <h2 className="text-xl sm:text-2xl font-bold text-white">Alarm Distribution</h2>
            </div>
            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white/10 text-gray-300 border border-white/10">
              {alarmStats?.total ?? 0} Total
            </span>
          </div>
          {alarmChartData.length > 0 ? (
            <div className="relative min-h-[260px]">
              <Chart data={alarmChartData} type="pie" height={260} showLegend={true} />
            </div>
          ) : (
            <div className="flex items-center justify-center min-h-[260px] rounded-xl border border-dashed border-gray-600/50 bg-gray-800/20">
              <p className="text-sm text-gray-500">No alarm data available</p>
            </div>
          )}
        </div>

        {/* Risk Level Distribution */}
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
          <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" aria-hidden />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-violet-400/90 mb-1">By risk level</p>
              <h2 className="text-xl sm:text-2xl font-bold text-white">Risk Level Distribution</h2>
            </div>
            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-white/10 text-gray-300 border border-white/10">
              {diagnostics?.length ?? diagnosticStats?.total ?? 0} Reports
            </span>
          </div>
          {diagnosticChartData.length > 0 ? (
            <div className="relative min-h-[260px]">
              <Chart data={diagnosticChartData} type="pie" height={260} showLegend={true} />
            </div>
          ) : (
            <div className="flex items-center justify-center min-h-[260px] rounded-xl border border-dashed border-gray-600/50 bg-gray-800/20">
              <p className="text-sm text-gray-500">No diagnostic data available</p>
            </div>
          )}
        </div>
        </div>
      </section>

      {/* System Resources */}
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
        <p className="text-xs font-medium uppercase tracking-[0.15em] text-gray-400 mb-2">Host metrics</p>
        <h2 className="text-xl sm:text-2xl font-bold text-white mb-6">System Resources</h2>
        {loadingMetrics && !systemMetrics ? (
          <p className="text-gray-400 text-sm">Loading...</p>
        ) : systemMetrics ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
            {/* CPU */}
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-5 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <span className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400">
                  <Cpu size={22} strokeWidth={1.5} />
                </span>
                <h3 className="text-lg font-semibold text-white">CPU</h3>
              </div>
              <div className="space-y-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm text-gray-400 uppercase tracking-wider">Usage</span>
                  <span className="text-xl font-bold text-white tabular-nums">{systemMetrics.cpu.usage_percent.toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 bg-gray-700/80 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(systemMetrics.cpu.usage_percent, 100)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Cores: {systemMetrics.cpu.count}</span>
                  {systemMetrics.cpu.frequency_mhz != null && (
                    <span className="tabular-nums">{systemMetrics.cpu.frequency_mhz.toFixed(0)} MHz</span>
                  )}
                </div>
              </div>
            </div>

            {/* Memory */}
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-5 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <span className="flex items-center justify-center w-10 h-10 rounded-lg bg-green-500/20 text-green-400">
                  <HardDrive size={22} strokeWidth={1.5} />
                </span>
                <h3 className="text-lg font-semibold text-white">Memory</h3>
              </div>
              <div className="space-y-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm text-gray-400 uppercase tracking-wider">Usage</span>
                  <span className="text-xl font-bold text-white tabular-nums">{systemMetrics.memory.usage_percent.toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 bg-gray-700/80 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(systemMetrics.memory.usage_percent, 100)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span className="tabular-nums">Used: {systemMetrics.memory.used_gb.toFixed(1)} GB</span>
                  <span className="tabular-nums">Total: {systemMetrics.memory.total_gb.toFixed(1)} GB</span>
                </div>
              </div>
            </div>

            {/* Network */}
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-5 flex flex-col gap-4 sm:col-span-2 lg:col-span-1">
              <div className="flex items-center gap-3">
                <span className="flex items-center justify-center w-10 h-10 rounded-lg bg-purple-500/20 text-purple-400">
                  <Network size={22} strokeWidth={1.5} />
                </span>
                <h3 className="text-lg font-semibold text-white">Network</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Sent</p>
                  <p className="text-lg font-bold text-white tabular-nums">{systemMetrics.network.bytes_sent_mb.toFixed(2)} MB</p>
                  <p className="text-xs text-gray-500 mt-0.5">{systemMetrics.network.packets_sent.toLocaleString()} packets</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Received</p>
                  <p className="text-lg font-bold text-white tabular-nums">{systemMetrics.network.bytes_recv_mb.toFixed(2)} MB</p>
                  <p className="text-xs text-gray-500 mt-0.5">{systemMetrics.network.packets_recv.toLocaleString()} packets</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-gray-400 text-sm">No system metrics available</p>
        )}
      </section>

      {/* Device Statistics */}
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
        <p className="text-xs font-medium uppercase tracking-[0.15em] text-gray-400 mb-2">Device status</p>
        <h2 className="text-xl sm:text-2xl font-bold text-white mb-6">Device Statistics</h2>
        {deviceStats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-5">
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-4 sm:p-5 flex flex-col gap-2">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Active</p>
              <p className="text-2xl sm:text-3xl font-bold text-green-400 tabular-nums">{deviceStats.by_status?.active ?? 0}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-4 sm:p-5 flex flex-col gap-2">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Inactive</p>
              <p className="text-2xl sm:text-3xl font-bold text-red-400 tabular-nums">{deviceStats.by_status?.inactive ?? 0}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-4 sm:p-5 flex flex-col gap-2">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Registered</p>
              <p className="text-2xl sm:text-3xl font-bold text-blue-400 tabular-nums">{deviceStats.by_status?.registered ?? 0}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-gray-800/40 p-4 sm:p-5 flex flex-col gap-2">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">Total</p>
              <p className="text-2xl sm:text-3xl font-bold text-white tabular-nums">{deviceStats.total ?? 0}</p>
            </div>
          </div>
        ) : (
          <p className="text-gray-400 text-sm">Loading...</p>
        )}
      </section>

      {/* Recent Activity */}
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
        <p className="text-xs font-medium uppercase tracking-[0.15em] text-gray-400 mb-2">Timeline</p>
        <h2 className="text-xl sm:text-2xl font-bold text-white mb-6">Recent Activity</h2>
        <div className="flex flex-col items-center justify-center py-12 rounded-xl border border-dashed border-gray-600/50 bg-gray-800/20">
          <p className="text-sm text-gray-500">Activity timeline will be displayed here</p>
        </div>
      </section>
    </div>
  );
};

