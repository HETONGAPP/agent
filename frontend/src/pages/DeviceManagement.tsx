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
import { FilterSelect } from '@/components/ui/FilterSelect';
import { SearchInput } from '@/components/ui/SearchInput';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { StatusIndicator } from '@/components/ui/StatusIndicator';
import { Device, DeviceFilters } from '@/types';
import { DEVICE_TYPES, DEVICE_STATUS, REFRESH_INTERVALS, REFRESH_DEBOUNCE_MS } from '@/config/constants';
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/date';
import { formatDeviceId } from '@/utils/format';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin, RefreshCw } from 'lucide-react';
import { PageLoading } from '@/components/ui/PageLoading';

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
  const [initialLoading, setInitialLoading] = useState(true);

  const [filters, setLocalFilters] = useState<DeviceFilters>({});
  const [selectedDeviceType, setSelectedDeviceType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Initial data fetch on mount
  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      try {
        await Promise.all([
          fetchDevices(),
          fetchStats(),
        ]);
      } finally {
        setInitialLoading(false);
      }
    };
    loadInitialData();
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
        }, REFRESH_DEBOUNCE_MS);
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
        }, REFRESH_DEBOUNCE_MS);
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
    enabled: !connected,
    interval: REFRESH_INTERVALS.DEVICE_FALLBACK,
    onUpdate: () => {
      if (!loading) {
        fetchDevices(filters);
        fetchStats();
      }
    },
  });

  const applyFilters = (typeOverride?: string, statusOverride?: string) => {
    const type = typeOverride !== undefined ? typeOverride : selectedDeviceType;
    const status = statusOverride !== undefined ? statusOverride : selectedStatus;
    const newFilters: DeviceFilters = {};
    if (type) newFilters.device_type = type as any;
    if (status) newFilters.status = status as any;
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

  // Show loading state during initial data fetch
  if (initialLoading) {
    return <PageLoading message="Loading devices..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1">Device Management</h1>
            <p className="text-gray-400 text-sm">Manage and monitor all devices</p>
          </div>
          {connected ? (
            <span className="flex items-center gap-2 text-sm text-green-400 ml-0 sm:ml-4">
              <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse"></span>
              Live
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            variant="secondary"
            onClick={() => fetchDevices(filters)}
            className="text-sm sm:text-base"
          >
            <RefreshCw size={16} className="sm:mr-2" />
            <span className="hidden sm:inline">Refresh</span>
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
            placeholder="Search devices..."
            onSearch={handleSearch}
          />
        }
      >
        <div className="hidden sm:flex items-center gap-x-4 gap-y-2 flex-wrap">
          <FilterSelect
            label="Type"
            value={selectedDeviceType}
            onChange={(v) => {
              setSelectedDeviceType(v);
              applyFilters(v, selectedStatus);
            }}
            options={Object.values(DEVICE_TYPES).map((t) => ({ value: t, label: t }))}
            placeholder="All types"
          />
          <FilterSelect
            label="Status"
            value={selectedStatus}
            onChange={(v) => {
              setSelectedStatus(v);
              applyFilters(selectedDeviceType, v);
            }}
            options={Object.values(DEVICE_STATUS).map((s) => ({ value: s, label: s }))}
            placeholder="All statuses"
          />
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
