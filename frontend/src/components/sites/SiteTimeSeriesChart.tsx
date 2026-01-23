/**
 * Site Time Series Chart Component
 * Displays device time series data with controls
 */

import { useMemo } from 'react';
import { Activity } from 'lucide-react';
import { TimeSeriesChartMemo } from '@/components/ui/TimeSeriesChart';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { DeviceTimeSeriesDataPoint } from '@/api/metrics';
import { Device } from '@/types';

interface SiteTimeSeriesChartProps {
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
  devices: Device[];
  siteId: string | undefined;
}

export const SiteTimeSeriesChart = ({
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
  devices,
  siteId,
}: SiteTimeSeriesChartProps) => {
  // No filters - use all devices directly
  const filteredDevices = devices;

  // Format time series data for TimeSeriesChart component
  // No longer combines data - each device shows separately
  const formattedChartData = useMemo((): Array<{ timestamp: string; value: number; device_id?: string }> => {
    try {
      if (deviceTimeSeries.length === 0) return [];

      // Filter data points for selected devices only
      const filtered = deviceTimeSeries.filter(point => 
        point.device_id && selectedDevices.includes(point.device_id)
      );

      const sorted = [...filtered]
        .filter(point => {
          if (!point || !point.timestamp) return false;
          const value = point.value;
          if (value === null || value === undefined || isNaN(value) || !isFinite(value)) return false;
          const timestamp = new Date(point.timestamp);
          if (isNaN(timestamp.getTime())) return false;
          return true;
        })
        .sort((a, b) => {
          try {
            return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          } catch (e) {
            return 0;
          }
        });

      // Return data as-is, no combining/averaging
      return sorted.map(point => ({
        timestamp: point.timestamp,
        value: point.value,
        device_id: point.device_id,
      }));
    } catch (error) {
      console.error('[SiteTimeSeriesChart] Error formatting chart data:', error);
      return [];
    }
  }, [deviceTimeSeries, selectedDevices]);

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-700/50">
        <Activity className="text-blue-400" size={20} />
        <h3 className="text-xl font-semibold text-white">Device Data Over Time</h3>
      </div>

      {/* Selection Controls */}
      <div className="mb-6">
        {/* Filters - Responsive layout: 4 columns on large screens, 2 rows on medium, 1 column on small */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Device</label>
            <select
              value={selectedDevices[0] || ''}
              onChange={(e) => {
                const deviceId = e.target.value;
                if (deviceId) {
                  setSelectedDevices([deviceId]);
                } else {
                  setSelectedDevices([]);
                }
              }}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="">Select device...</option>
              {filteredDevices.map((device) => (
                <option key={device.device_id} value={device.device_id}>
                  {device.device_id} ({device.device_type} - {device.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Metric</label>
            <select
              value={selectedMetric}
              onChange={(e) => {
                const newMetric = e.target.value;
                setSelectedMetric(newMetric);
                if (newMetric && selectedDevices.length === 0 && filteredDevices.length > 0) {
                  setSelectedDevices([filteredDevices[0].device_id]);
                }
              }}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="">Select metric...</option>
              {availableMetrics.map((metric) => (
                <option key={metric} value={metric}>
                  {metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Time Range</label>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="-1h">Last 1 hour</option>
              <option value="-6h">Last 6 hours</option>
              <option value="-24h">Last 24 hours</option>
              <option value="-7d">Last 7 days</option>
              <option value="-30d">Last 30 days</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Interval</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            >
              <option value="1m">1 minute</option>
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
              <option value="1h">1 hour</option>
              <option value="1d">1 day</option>
            </select>
          </div>
        </div>
      </div>

      {/* Chart */}
      {loadingTimeSeries ? (
        <div className="flex items-center justify-center h-[300px] text-gray-400">
          <LoadingSpinner />
        </div>
      ) : selectedDevices.length === 0 || !selectedMetric ? (
        <div className="flex items-center justify-center h-[300px] text-gray-400">
          <div className="text-center">
            <Activity size={48} className="mx-auto mb-4 text-gray-600" />
            <p className="text-lg mb-2">No data selected</p>
            <p className="text-sm">Please select devices and a metric to view data</p>
          </div>
        </div>
      ) : formattedChartData.length > 0 ? (
        <div className="transition-opacity duration-300">
          <div className="mb-4 text-sm text-gray-400 flex items-center justify-between">
            <span>
              Showing {formattedChartData.length} data points
              {selectedDevices.length > 0 && ` for device: ${selectedDevices[0]}`}
            </span>
            <span className="text-xs text-gray-500">
              Metric: <span className="text-blue-400 font-medium">{selectedMetric}</span>
            </span>
          </div>
          <div className="relative">
            {(() => {
              try {
                return (
                  <TimeSeriesChartMemo
                    data={formattedChartData}
                    height={400}
                    color="#3B82F6"
                    showGrid={true}
                    realTime={true}
                  />
                );
              } catch (error) {
                console.error('[SiteTimeSeriesChart] Error rendering chart:', error);
                return (
                  <div className="flex items-center justify-center h-[400px] text-red-400">
                    <div className="text-center">
                      <Activity size={48} className="mx-auto mb-4 text-red-600" />
                      <p className="text-lg mb-2">Chart rendering error</p>
                      <p className="text-sm mb-2">Error: {error instanceof Error ? error.message : String(error)}</p>
                    </div>
                  </div>
                );
              }
            })()}
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center h-[300px] text-gray-400">
          <div className="text-center">
            <Activity size={48} className="mx-auto mb-4 text-gray-600" />
            <p className="text-lg mb-2">No data available</p>
            <p className="text-sm mb-2">No data found for selected devices and metric</p>
            <p className="text-xs text-gray-500 mt-2">
              Site: {siteId} | Devices: {selectedDevices.join(', ')} | Metric: {selectedMetric}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

