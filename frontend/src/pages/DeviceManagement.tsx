/**
 * Device Management Page
 * Displays and manages devices
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useDevices } from '@/hooks/useDevices';
import { useRealtime } from '@/hooks/useRealtime';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { DataTable, Column } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { StatusIndicator } from '@/components/ui/StatusIndicator';
import { Device, DeviceFilters } from '@/types';
import { DEVICE_TYPES, DEVICE_STATUS } from '@/config/constants';
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/date';
import { formatDeviceId } from '@/utils/format';
import { exportDevices } from '@/utils/export';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';

export const DeviceManagement = () => {
  const {
    devices,
    stats,
    loading,
    error,
    fetchDevices,
    fetchStats,
    setFilters,
  } = useDevices(true);
  const { addToast } = useToastStore();

  const [filters, setLocalFilters] = useState<DeviceFilters>({});
  const [selectedDeviceType, setSelectedDeviceType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Initial data fetch on mount
  useEffect(() => {
    fetchDevices();
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // WebSocket for real-time updates
  // Use useMemo to prevent events array from being recreated on every render
  const wsEvents = useMemo<EventType[]>(
    () => ['device_status_changed', 'device_added', 'device_removed', 'device_updated', 'stats_updated'],
    []
  );

  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents,
    onMessage: useCallback(() => {
      // Event manager will handle this
    }, []),
    onConnect: useCallback(() => {
      console.log('WebSocket connected, fetching data');
      // Always fetch data when WebSocket connects (ensures fresh data)
      fetchDevices(filters);
      fetchStats();
    }, [filters, fetchDevices, fetchStats]),
    onDisconnect: useCallback(() => {
      // Silently handle disconnect
    }, []),
    onError: useCallback(() => {
      // Silently handle errors
    }, []),
  });

  // Subscribe to WebSocket events via event manager
  useEffect(() => {
    // Debounce timer for device list refresh
    let deviceRefreshTimer: ReturnType<typeof setTimeout> | null = null;
    
    const unsubscribeDeviceStatusChanged = websocketEventManager.subscribe(EventType.DEVICE_STATUS_CHANGED, (data) => {
      // Only refresh device list if device_id is provided (specific device changed)
      // Otherwise, just refresh stats to avoid unnecessary refreshes
      if (data?.device_id) {
        // Debounce device list refresh to avoid rapid updates
        if (deviceRefreshTimer) {
          clearTimeout(deviceRefreshTimer);
        }
        deviceRefreshTimer = setTimeout(() => {
          fetchDevices(filters);
          fetchStats();
        }, 500); // 500ms debounce
      } else {
        // No specific device, just refresh stats
        fetchStats();
      }
    });
    
    const unsubscribeDeviceAdded = websocketEventManager.subscribe(EventType.DEVICE_ADDED, () => {
      // Debounce device list refresh
      if (deviceRefreshTimer) {
        clearTimeout(deviceRefreshTimer);
      }
      deviceRefreshTimer = setTimeout(() => {
        fetchDevices(filters);
        fetchStats();
      }, 300);
    });
    
    const unsubscribeDeviceRemoved = websocketEventManager.subscribe(EventType.DEVICE_REMOVED, () => {
      // Debounce device list refresh
      if (deviceRefreshTimer) {
        clearTimeout(deviceRefreshTimer);
      }
      deviceRefreshTimer = setTimeout(() => {
        fetchDevices(filters);
        fetchStats();
      }, 300);
    });
    
    const unsubscribeDeviceUpdated = websocketEventManager.subscribe(EventType.DEVICE_UPDATED, (data) => {
      // Device information was updated (metadata, integration_name, etc.)
      // Force refresh device list to show updated information
      if (data?.device_id) {
        // Invalidate cache for devices
        import('@/services/dataService').then(({ dataService }) => {
          dataService.invalidateCache('devices');
        });
      }
      
      // Always refresh device list to ensure consistency
      // Use shorter debounce for device updates to show changes faster
      if (deviceRefreshTimer) {
        clearTimeout(deviceRefreshTimer);
      }
      deviceRefreshTimer = setTimeout(() => {
        // Force refresh by passing forceUpdate flag to bypass comparison
        fetchDevices(filters, undefined, undefined, true);
        fetchStats();
      }, 200); // Reduced debounce time for device updates
    });
    
    const unsubscribeStatsUpdated = websocketEventManager.subscribe(EventType.STATS_UPDATED, (data) => {
      // Only refresh stats, not device list
      // This prevents flickering when status is recalculated
      fetchStats();
      
      // Only refresh device list if explicitly requested (e.g., device_added/removed)
      // Periodic status checks should not trigger device list refresh
      if (data?.reason === 'device_added' || data?.reason === 'device_removed' || data?.device_id) {
        if (deviceRefreshTimer) {
          clearTimeout(deviceRefreshTimer);
        }
        deviceRefreshTimer = setTimeout(() => {
          fetchDevices(filters);
        }, 500);
      }
    });

    return () => {
      unsubscribeDeviceStatusChanged();
      unsubscribeDeviceAdded();
      unsubscribeDeviceRemoved();
      unsubscribeDeviceUpdated();
      unsubscribeStatsUpdated();
      if (deviceRefreshTimer) {
        clearTimeout(deviceRefreshTimer);
      }
    };
  }, [filters, fetchDevices, fetchStats]);

  // Fallback polling (only if WebSocket is not connected)
  useRealtime({
    enabled: !connected, // Only use polling if WebSocket is not connected
    interval: 30000, // 30 seconds
    onUpdate: () => {
      if (!loading) {
        fetchDevices(filters);
        fetchStats();
      }
    },
  });

  const handleFilterChange = () => {
    const newFilters: DeviceFilters = {};
    if (selectedDeviceType) {
      newFilters.device_type = selectedDeviceType as any;
    }
    if (selectedStatus) {
      newFilters.status = selectedStatus as any;
    }
    setLocalFilters(newFilters);
    setFilters(newFilters);
    fetchDevices(newFilters);
  };

  const handleClearFilters = () => {
    setSelectedDeviceType('');
    setSelectedStatus('');
    setLocalFilters({});
    setFilters({});
    fetchDevices();
  };


  const handleExport = () => {
    try {
      exportDevices(devices);
      addToast('Devices exported successfully', 'success');
    } catch (error) {
      addToast('Failed to export devices', 'error');
    }
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    // Filter devices client-side for now
    // In production, you might want to send search query to backend
  };

  // Filter devices by search query
  const filteredDevices = searchQuery
    ? devices.filter((device) =>
        device.device_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        device.device_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        device.integration_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : devices;

  const columns: Column<Device>[] = [
    {
      key: 'device_id',
      header: 'Device ID',
      render: (device) => (
        <span className="font-mono text-blue-400">{formatDeviceId(device.device_id)}</span>
      ),
    },
    {
      key: 'site_id',
      header: 'Site',
      render: (device) => {
        const siteId = (device.metadata as any)?.site_id;
        if (siteId) {
          return (
            <Link
              to={`/datacenter/sites/${siteId}`}
              className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 hover:underline transition-colors"
            >
              <MapPin size={14} className="text-gray-400" />
              <span className="font-mono text-sm">{siteId}</span>
            </Link>
          );
        }
        return (
          <span className="text-gray-500 text-sm flex items-center gap-1.5">
            <MapPin size={14} className="text-gray-600" />
            N/A
          </span>
        );
      },
    },
    {
      key: 'device_type',
      header: 'Type',
      render: (device) => (
        <Badge type="status" value={device.device_type} size="sm" />
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (device) => (
        <StatusIndicator status={device.status} size="md" showLabel={true} />
      ),
    },
    {
      key: 'brand',
      header: 'Brand/Manufacturer',
      render: (device) => {
        const brand = (device.metadata as any)?.brand || 
                     (device.metadata as any)?.manufacturer ||
                     'N/A';
        return (
          <span className="text-gray-300 text-sm">{brand}</span>
        );
      },
    },
    {
      key: 'integration_name',
      header: 'Manufacturing ID',
      render: (device) => {
        // Try to get manufacturing_id from metadata, fallback to integration_name
        const manufacturingId = (device.metadata as any)?.manufacturing_id || 
                                (device.metadata as any)?.manufacture_id ||
                                device.integration_name;
        return (
          <span className="text-gray-300 font-mono text-sm">{manufacturingId || 'N/A'}</span>
        );
      },
    },
    {
      key: 'registered_at',
      header: 'Registration Time',
      render: (device) => (
        <span className="text-gray-300 text-sm">
          {device.registered_at ? formatAbsoluteTime(device.registered_at) : 'N/A'}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-1">Device Management</h1>
            <p className="text-gray-400 text-sm">Manage and monitor all devices</p>
          </div>
          {connected ? (
            <span className="flex items-center gap-2 text-sm text-green-400 ml-4">
              <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse"></span>
              Live
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleExport} disabled={devices.length === 0}>
            Export CSV
          </Button>
          <Button variant="secondary" onClick={() => fetchDevices(filters)}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="text-sm text-gray-400">Total Devices</div>
            <div className="text-2xl font-bold text-white">{stats.total}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Active</div>
            <div className="text-2xl font-bold text-green-400">{stats.by_status?.active || 0}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Inactive</div>
            <div className="text-2xl font-bold text-red-400">{stats.by_status?.inactive || 0}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Registered</div>
            <div className="text-2xl font-bold text-blue-400">{stats.by_status?.registered || 0}</div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <FilterBar 
        onClear={handleClearFilters}
        searchComponent={
          <SearchInput
            placeholder="Search devices by ID, type, or integration..."
            onSearch={handleSearch}
          />
        }
      >
          {/* Filter Group - Fixed width to prevent shifting */}
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg whitespace-nowrap flex-shrink-0">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
            <div className="h-4 w-px bg-gray-700"></div>
            
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Device Type</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[140px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={selectedDeviceType}
                onChange={(e) => setSelectedDeviceType(e.target.value)}
              >
                <option value="">All Types</option>
                {Object.values(DEVICE_TYPES).map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div className="h-4 w-px bg-gray-700"></div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Status</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[120px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
              >
                <option value="">All Statuses</option>
                {Object.values(DEVICE_STATUS).map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <Button variant="primary" size="sm" onClick={handleFilterChange}>
              Apply Filters
            </Button>
          </div>
        </FilterBar>

      {/* Error Message */}
      {error && (
        <div className="card border-red-500 bg-red-500/10">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Device Table */}
      <DataTable<Device>
        data={filteredDevices}
        columns={columns}
        loading={loading}
        emptyMessage="No devices found"
      />

    </div>
  );
};
