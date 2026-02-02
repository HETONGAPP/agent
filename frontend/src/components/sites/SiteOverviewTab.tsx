/**
 * Site Overview Tab Component
 * Displays site overview with statistics and time series chart
 */

import { Settings, Plug, CheckCircle, AlertCircle, AlertTriangle } from 'lucide-react';
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
      {/* Overview stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-blue-500/30 sm:hover:shadow-blue-500/5 transition-all duration-300">
            <div className="relative flex flex-col gap-4">
              <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-500/20 text-blue-400 sm:shadow-lg sm:shadow-blue-500/10" aria-hidden>
                <Plug size={24} strokeWidth={1.5} />
              </span>
              <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
                {stats.devices.total}
              </p>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Total Devices</p>
            </div>
          </div>
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-green-500/30 sm:hover:shadow-green-500/5 transition-all duration-300">
            <div className="relative flex flex-col gap-4">
              <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-green-500/20 text-green-400 sm:shadow-lg sm:shadow-green-500/10" aria-hidden>
                <CheckCircle size={24} strokeWidth={1.5} />
              </span>
              <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
                {stats.devices.by_status?.active ?? 0}
              </p>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Active Devices</p>
            </div>
          </div>
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-amber-500/30 sm:hover:shadow-amber-500/5 transition-all duration-300">
            <div className="relative flex flex-col gap-4">
              <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-amber-500/20 text-amber-400 sm:shadow-lg sm:shadow-amber-500/10" aria-hidden>
                <AlertCircle size={24} strokeWidth={1.5} />
              </span>
              <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
                {stats.alarms.total}
              </p>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Total Alarms</p>
            </div>
          </div>
          <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gray-800/30 backdrop-blur-md p-5 sm:p-6 min-w-0 sm:shadow-xl sm:shadow-black/20 hover:border-red-500/30 sm:hover:shadow-red-500/5 transition-all duration-300">
            <div className="relative flex flex-col gap-4">
              <span className="flex items-center justify-center w-12 h-12 rounded-xl bg-red-500/20 text-red-400 sm:shadow-lg sm:shadow-red-500/10" aria-hidden>
                <AlertTriangle size={24} strokeWidth={1.5} />
              </span>
              <p className="text-3xl sm:text-4xl font-bold text-white tabular-nums tracking-tight">
                {stats.alarms.by_severity?.Critical ?? 0}
              </p>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Critical Alarms</p>
            </div>
          </div>
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
      <div className="rounded-2xl border border-white/10 bg-gray-800/20 backdrop-blur-md p-6 sm:p-8 sm:shadow-xl sm:shadow-black/20">
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

