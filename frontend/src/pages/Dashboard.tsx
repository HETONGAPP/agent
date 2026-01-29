/**
 * Dashboard Page
 * Main overview page with statistics and recent activity
 */

import { useEffect, useCallback, useState } from 'react';
import { StatCard } from '@/components/ui/StatCard';
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
    <div className="space-y-3 sm:space-y-4 lg:space-y-6 w-full" style={{ maxWidth: '100%', boxSizing: 'border-box' }}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1">Dashboard</h1>
          <p className="text-gray-400 text-xs sm:text-sm">System overview and statistics</p>
        </div>
        {/* Weather Widget */}
        {!userLocation ? (
          <div className="flex items-center gap-2 text-gray-400 text-xs sm:text-sm">
            <Cloud size={14} className="sm:w-4 sm:h-4" />
            <span className="hidden sm:inline">Location permission needed for weather</span>
            <span className="sm:hidden">Location needed</span>
          </div>
        ) : loadingWeather ? (
          <div className="flex items-center gap-2 text-gray-400">
            <Cloud size={18} className="sm:w-5 sm:h-5" />
            <span className="text-xs sm:text-sm">Loading...</span>
          </div>
        ) : weather ? (
          <div className="flex items-center gap-2 sm:gap-3 bg-gray-800/50 rounded-lg px-3 sm:px-4 py-2 border border-gray-700/50">
            <div className="flex items-center gap-2">
              {weather.icon && (
                <img
                  src={`https://openweathermap.org/img/wn/${weather.icon}@2x.png`}
                  alt={weather.description}
                  className="w-8 h-8 sm:w-10 sm:h-10"
                  onError={(e) => {
                    // Fallback to icon if image fails to load
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
              <div className="flex flex-col">
                <div className="flex items-center gap-1 sm:gap-2">
                  <span className="text-xl sm:text-2xl font-bold text-white">{weather.temperature}°C</span>
                  <Cloud className="text-blue-400 sm:w-5 sm:h-5" size={16} />
                </div>
                <div className="text-xs text-gray-400">
                  {weather.city}{weather.country && `, ${weather.country}`}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
      
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 lg:gap-6">
        <StatCard
          title="Total Devices"
          value={formatNumber(deviceStats?.total || 0)}
          icon={Plug}
          color="blue"
        />
        <StatCard
          title="Active Alarms"
          value={formatNumber(alarmStats?.total || 0)}
          icon={Bell}
          color="red"
        />
        <StatCard
          title="Diagnostic Reports"
          value={formatNumber(diagnostics?.length || diagnosticStats?.total || 0)}
          icon={FileText}
          color="purple"
        />
        <StatCard
          title="Critical Alarms"
          value={formatNumber(alarmStats?.by_severity?.Critical || 0)}
          icon={AlertTriangle}
          color="red"
        />
      </div>

      {/* Detailed Statistics with Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 lg:gap-6">
        {/* Alarm Statistics Chart */}
        <div className="card bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700/50 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">Alarm Distribution</h2>
            <div className="text-xs text-gray-400 bg-gray-800/50 px-2 py-1 rounded">
              {alarmStats?.total || 0} Total
            </div>
          </div>
          {alarmChartData.length > 0 ? (
            <Chart data={alarmChartData} type="pie" height={240} showLegend={true} />
          ) : (
            <div className="flex items-center justify-center h-[240px] text-gray-400">
              <div className="text-center">
                <div className="text-4xl mb-2">📊</div>
                <div>No alarm data available</div>
              </div>
            </div>
          )}
        </div>

        {/* Diagnostic Statistics Chart */}
        <div className="card bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700/50 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">Risk Level Distribution</h2>
            <div className="text-xs text-gray-400 bg-gray-800/50 px-2 py-1 rounded">
              {diagnostics?.length || diagnosticStats?.total || 0} Reports
            </div>
          </div>
          {diagnosticChartData.length > 0 ? (
            <Chart data={diagnosticChartData} type="pie" height={240} showLegend={true} />
          ) : (
            <div className="flex items-center justify-center h-[240px] text-gray-400">
              <div className="text-center">
                <div className="text-4xl mb-2">📊</div>
                <div>No diagnostic data available</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* System Resources */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">System Resources</h2>
        {loadingMetrics && !systemMetrics ? (
          <p className="text-gray-400">Loading...</p>
        ) : systemMetrics ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 lg:gap-6">
            {/* CPU */}
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
              <div className="flex items-center gap-3 mb-3">
                <Cpu className="text-blue-400" size={20} />
                <h3 className="text-lg font-semibold text-white">CPU</h3>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Usage</span>
                  <span className="text-lg font-bold text-white">{systemMetrics.cpu.usage_percent.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${systemMetrics.cpu.usage_percent}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400 mt-2">
                  <span>Cores: {systemMetrics.cpu.count}</span>
                  {systemMetrics.cpu.frequency_mhz && (
                    <span>{systemMetrics.cpu.frequency_mhz.toFixed(0)} MHz</span>
                  )}
                </div>
              </div>
            </div>

            {/* Memory */}
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
              <div className="flex items-center gap-3 mb-3">
                <HardDrive className="text-green-400" size={20} />
                <h3 className="text-lg font-semibold text-white">Memory</h3>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Usage</span>
                  <span className="text-lg font-bold text-white">{systemMetrics.memory.usage_percent.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${systemMetrics.memory.usage_percent}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400 mt-2">
                  <span>Used: {systemMetrics.memory.used_gb.toFixed(1)} GB</span>
                  <span>Total: {systemMetrics.memory.total_gb.toFixed(1)} GB</span>
                </div>
              </div>
            </div>

            {/* Network Throughput */}
            <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
              <div className="flex items-center gap-3 mb-3">
                <Network className="text-purple-400" size={20} />
                <h3 className="text-lg font-semibold text-white">Network</h3>
              </div>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-400">Sent</span>
                    <span className="text-sm font-semibold text-white">{systemMetrics.network.bytes_sent_mb.toFixed(2)} MB</span>
                  </div>
                  <div className="text-xs text-gray-500">{systemMetrics.network.packets_sent.toLocaleString()} packets</div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-400">Received</span>
                    <span className="text-sm font-semibold text-white">{systemMetrics.network.bytes_recv_mb.toFixed(2)} MB</span>
                  </div>
                  <div className="text-xs text-gray-500">{systemMetrics.network.packets_recv.toLocaleString()} packets</div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-gray-400">No system metrics available</p>
        )}
      </div>

      {/* Device Statistics */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Device Statistics</h2>
        {deviceStats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-400">Active</div>
              <div className="text-2xl font-bold text-green-400">{deviceStats.by_status?.active || 0}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Inactive</div>
              <div className="text-2xl font-bold text-red-400">{deviceStats.by_status?.inactive || 0}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Registered</div>
              <div className="text-2xl font-bold text-blue-400">{deviceStats.by_status?.registered || 0}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Total</div>
              <div className="text-2xl font-bold text-white">{deviceStats.total}</div>
            </div>
          </div>
        ) : (
          <p className="text-gray-400">Loading...</p>
        )}
      </div>
      
      {/* Recent Activity */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
        <p className="text-gray-400">Activity timeline will be displayed here</p>
      </div>
    </div>
  );
};

