/**
 * Site Overview Tab Component
 * Displays site overview with statistics and time series chart
 */

import { Settings } from 'lucide-react';
import { StatCard } from '@/components/ui/StatCard';
import { Plug, CheckCircle, AlertCircle, AlertTriangle } from 'lucide-react';
import { SiteTimeSeriesChart } from './SiteTimeSeriesChart';
import { DeviceTimeSeriesDataPoint } from '@/api/metrics';
import { Device } from '@/types';

interface SiteOverviewTabProps {
  selectedSite: any;
  stats: any;
  devices: Device[];
  deviceTimeSeries: DeviceTimeSeriesDataPoint[];
  loadingTimeSeries: boolean;
  selectedDevices: string[];
  setSelectedDevices: (devices: string[]) => void;
  selectedMetric: string;
  setSelectedMetric: (metric: string) => void;
  timeRange: string;
  setTimeRange: (range: string) => void;
  interval: string;
  setInterval: (interval: string) => void;
  availableMetrics: string[];
  siteId: string | undefined;
}

export const SiteOverviewTab = ({
  selectedSite,
  stats,
  devices,
  deviceTimeSeries,
  loadingTimeSeries,
  selectedDevices,
  setSelectedDevices,
  selectedMetric,
  setSelectedMetric,
  timeRange,
  setTimeRange,
  interval,
  setInterval,
  availableMetrics,
  siteId,
}: SiteOverviewTabProps) => {
  return (
    <div className="space-y-6">
      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Devices"
            value={stats.devices.total.toString()}
            icon={Plug}
            color="blue"
          />
          <StatCard
            title="Active Devices"
            value={(stats.devices.by_status.active || 0).toString()}
            icon={CheckCircle}
            color="green"
          />
          <StatCard
            title="Total Alarms"
            value={stats.alarms.total.toString()}
            icon={AlertCircle}
            color="red"
          />
          <StatCard
            title="Critical Alarms"
            value={(stats.alarms.by_severity.Critical || 0).toString()}
            icon={AlertTriangle}
            color="red"
          />
        </div>
      )}

      {/* Device Data Time Series Chart */}
      <SiteTimeSeriesChart
        deviceTimeSeries={deviceTimeSeries}
        loadingTimeSeries={loadingTimeSeries}
        selectedDevices={selectedDevices}
        setSelectedDevices={setSelectedDevices}
        selectedMetric={selectedMetric}
        setSelectedMetric={setSelectedMetric}
        timeRange={timeRange}
        setTimeRange={setTimeRange}
        interval={interval}
        setInterval={setInterval}
        availableMetrics={availableMetrics}
        devices={devices}
        siteId={siteId}
      />

      {/* Site Configuration */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-700/50">
          <Settings className="text-blue-400" size={20} />
          <h3 className="text-xl font-semibold text-white">Site Configuration</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(selectedSite.settings || {}).map(([key, value]) => (
            <div key={key} className="p-4 rounded-lg bg-gray-800/30 border border-gray-700/30 hover:border-gray-600/50 transition-colors">
              <div className="text-xs text-gray-400 mb-1.5 uppercase tracking-wider">{key.replace(/_/g, ' ')}</div>
              <div className="text-white font-medium text-lg">{String(value)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

