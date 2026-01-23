/**
 * Dashboard Page
 * Main overview page with statistics and recent activity
 */

import { useEffect, useCallback } from 'react';
import { StatCard } from '@/components/ui/StatCard';
import { Chart } from '@/components/ui/Chart';
import { useDevices } from '@/hooks/useDevices';
import { useAlarms } from '@/hooks/useAlarms';
import { useDiagnostics } from '@/hooks/useDiagnostics';
import { useRealtime } from '@/hooks/useRealtime';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { formatNumber } from '@/utils/format';
import { Plug, Bell, FileText, AlertTriangle } from 'lucide-react';

export const Dashboard = () => {
  const { stats: deviceStats, fetchStats: fetchDeviceStats } = useDevices(false);
  const { stats: alarmStats, fetchStats: fetchAlarmStats } = useAlarms(false);
  const { stats: diagnosticStats, fetchStats: fetchDiagnosticStats } = useDiagnostics(false);

  useEffect(() => {
    fetchDeviceStats();
    fetchAlarmStats();
    fetchDiagnosticStats();
  }, [fetchDeviceStats, fetchAlarmStats, fetchDiagnosticStats]);

  // WebSocket for real-time updates
  const wsEvents = useCallback(() => ['alarm_created', 'alarm_updated', 'stats_updated'], []);
  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents(),
    onMessage: useCallback((message) => {
      // Refresh stats when alarms are created/updated or stats are updated
      if (message.type === 'alarm_created' || message.type === 'alarm_updated' || message.type === 'stats_updated') {
        fetchAlarmStats();
        fetchDiagnosticStats();
        fetchDeviceStats();
      }
    }, [fetchAlarmStats, fetchDiagnosticStats, fetchDeviceStats]),
    onConnect: useCallback(() => {
      console.log('Dashboard: WebSocket connected, fetching data');
      fetchDeviceStats();
      fetchAlarmStats();
      fetchDiagnosticStats();
    }, [fetchDeviceStats, fetchAlarmStats, fetchDiagnosticStats]),
  });

  // Fallback polling (only when WebSocket is not connected)
  useRealtime({
    enabled: !connected,
    interval: 60000, // 60 seconds
    onUpdate: () => {
      fetchDeviceStats();
      fetchAlarmStats();
      fetchDiagnosticStats();
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

  const diagnosticChartData = diagnosticStats
    ? Object.entries(diagnosticStats.by_risk_level || {}).map(([label, value]) => ({
        label,
        value: value as number,
        color:
          label === 'High'
            ? '#DC2626'
            : label === 'Medium'
            ? '#EA580C'
            : '#16A34A',
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">Dashboard</h1>
          <p className="text-gray-400 text-sm">System overview and statistics</p>
        </div>
      </div>
      
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
          value={formatNumber(diagnosticStats?.total || 0)}
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
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Alarm Statistics Chart */}
        <div className="card bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700/50 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">Alarm Distribution</h2>
            <div className="text-xs text-gray-400 bg-gray-800/50 px-2 py-1 rounded">
              {alarmStats?.total || 0} Total
            </div>
          </div>
          {alarmChartData.length > 0 ? (
            <Chart data={alarmChartData} type="bar" height={240} showGrid={true} />
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
              {diagnosticStats?.total || 0} Reports
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

