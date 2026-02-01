/**
 * Alarm Management Page
 * Displays and manages alarms
 */

import { useState, useEffect, useCallback } from 'react';
import { useAlarms } from '@/hooks/useAlarms';
import { useRealtime } from '@/hooks/useRealtime';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { DataTable, Column } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { FilterSelect } from '@/components/ui/FilterSelect';
import { DateRangePicker } from '@/components/ui/DateRangePicker';
import { SearchInput } from '@/components/ui/SearchInput';
import { Pagination } from '@/components/ui/Pagination';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alarm, AlarmFilters } from '@/types';
import { ALARM_SEVERITY, REFRESH_INTERVALS, REFRESH_DEBOUNCE_MS } from '@/config/constants';
import { formatRelativeTime } from '@/utils/date';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin, Brain, RefreshCw } from 'lucide-react';
import { useSiteStore } from '@/store/useSiteStore';
import { DEVICE_TYPES } from '@/config/constants';
import { generateAlarmDiagnostic } from '@/api/diagnostics';
import { generateSiteDiagnostic } from '@/api/sites';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { PageLoading } from '@/components/ui/PageLoading';

export const AlarmManagement = () => {
  const {
    alarms,
    stats,
    pagination,
    loading,
    error,
    fetchAlarms,
    fetchStats,
    setFilters,
    setPagination,
  } = useAlarms(true);
  const [initialLoading, setInitialLoading] = useState(true);
  

  const { addToast } = useToastStore();
  const { sites } = useSiteStore(); // Sites are preloaded in App.tsx, no need to fetch here
  const [filters, setLocalFilters] = useState<AlarmFilters>({});
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedSiteId, setSelectedSiteId] = useState<string>('');
  const [selectedDeviceType, setSelectedDeviceType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [generatingDiagnostics, setGeneratingDiagnostics] = useState<Set<string>>(new Set());
  
  // Sync selectedSeverity with filters on mount
  useEffect(() => {
    if (filters.severity) {
      setSelectedSeverity(filters.severity);
    }
    if (filters.site_id) {
      setSelectedSiteId(filters.site_id);
    }
    if (filters.device_type) {
      setSelectedDeviceType(filters.device_type);
    }
  }, []);

  // WebSocket for real-time updates
  const wsEvents = useCallback(() => [
    EventType.ALARM_CREATED,
    EventType.ALARM_UPDATED,
    EventType.STATS_UPDATED,
  ] as EventType[], []);

  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents(),
    onMessage: useCallback(() => {
      // Event manager will handle this, but we keep this for backward compatibility
    }, []),
    onConnect: useCallback(() => {
      fetchAlarms(filters, pagination.limit, pagination.offset, true);
      fetchStats();
    }, [filters, pagination.limit, pagination.offset, fetchAlarms, fetchStats]),
    onDisconnect: useCallback(() => {
      // WebSocket disconnected
    }, []),
    onError: useCallback(() => {
      // Silently handle errors
    }, []),
  });

  // Subscribe to WebSocket events via event manager
  // Use debouncing to avoid too frequent refreshes
  useEffect(() => {
    let refreshTimeout: NodeJS.Timeout | null = null;
    
    const debouncedRefresh = () => {
      if (refreshTimeout) {
        clearTimeout(refreshTimeout);
      }
      refreshTimeout = setTimeout(() => {
        fetchAlarms(filters, pagination.limit, pagination.offset, true);
        fetchStats();
      }, REFRESH_DEBOUNCE_MS);
    };
    
    const unsubscribeAlarmCreated = websocketEventManager.subscribe(EventType.ALARM_CREATED, debouncedRefresh);
    const unsubscribeAlarmUpdated = websocketEventManager.subscribe(EventType.ALARM_UPDATED, debouncedRefresh);
    const unsubscribeStatsUpdated = websocketEventManager.subscribe(EventType.STATS_UPDATED, () => {
      fetchStats();
    });

    return () => {
      if (refreshTimeout) {
        clearTimeout(refreshTimeout);
      }
      unsubscribeAlarmCreated();
      unsubscribeAlarmUpdated();
      unsubscribeStatsUpdated();
    };
    }, [filters, pagination.limit, pagination.offset, fetchAlarms, fetchStats]);

  // Initial data fetch on mount - same pattern as Dashboard (full-page PageLoading until ready)
  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      const minDisplayMs = 300;
      const start = Date.now();
      try {
        await Promise.all([
          fetchAlarms(filters, pagination.limit, pagination.offset, true),
          fetchStats(),
        ]);
      } finally {
        const elapsed = Date.now() - start;
        const remaining = Math.max(0, minDisplayMs - elapsed);
        setTimeout(() => setInitialLoading(false), remaining);
      }
    };
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fallback polling (only when WebSocket is not connected)
  useRealtime({
    enabled: !connected && !loading,
    interval: REFRESH_INTERVALS.ALARM_FALLBACK,
    onUpdate: () => {
      if (!loading && !connected) {
        // Use localFilters which includes all active filters
        fetchAlarms(filters, pagination.limit, pagination.offset, true);
        fetchStats();
      }
    },
  });

  const applyFilters = (updates: Partial<AlarmFilters> = {}) => {
    const newFilters: AlarmFilters = { ...filters, ...updates };
    if (updates.severity !== undefined) newFilters.severity = updates.severity as any;
    else if (selectedSeverity) newFilters.severity = selectedSeverity as any;
    else delete newFilters.severity;
    if (updates.site_id !== undefined) newFilters.site_id = updates.site_id || undefined;
    else if (selectedSiteId) newFilters.site_id = selectedSiteId;
    else delete newFilters.site_id;
    if (updates.device_type !== undefined) newFilters.device_type = updates.device_type || undefined;
    else if (selectedDeviceType) newFilters.device_type = selectedDeviceType;
    else delete newFilters.device_type;
    setLocalFilters(newFilters);
    setFilters(newFilters);
    fetchAlarms(newFilters, pagination.limit, 0, true);
    setPagination(pagination.limit, 0);
  };

  const handleClearFilters = () => {
    setSelectedSeverity('');
    setSelectedSiteId('');
    setSelectedDeviceType('');
    setLocalFilters({});
    setFilters({});
    fetchAlarms({}, pagination.limit, 0, true);
    setPagination(pagination.limit, 0);
  };

  const handlePageChange = (page: number) => {
    const offset = (page - 1) * pagination.limit;
    setPagination(pagination.limit, offset);
    fetchAlarms(filters, pagination.limit, offset, true);
  };

  // Site summary columns
  const siteSummaryColumns: Column<any>[] = [
    {
      key: 'site_id',
      header: 'Site ID',
      render: (siteSummary: any) => {
        const sid = siteSummary.site_id;
        const isSystem = sid === '_system';
        const label = siteSummary.site_name || sid;
        if (isSystem) {
          return (
            <span className="flex items-center gap-1.5 text-gray-400">
              <MapPin size={14} className="text-gray-500" />
              <span className="font-mono text-sm font-semibold">{label}</span>
            </span>
          );
        }
        return (
          <Link
            to={`/datacenter/sites/${sid}`}
            className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 hover:underline transition-colors"
          >
            <MapPin size={14} className="text-gray-400" />
            <span className="font-mono text-sm font-semibold">{sid}</span>
          </Link>
        );
      },
    },
    {
      key: 'site_name',
      header: 'Site Name',
      render: (siteSummary: any) => (
        <span className="text-gray-300 font-medium">
          {siteSummary.site_name || siteSummary.site_id}
        </span>
      ),
    },
    {
      key: 'location',
      header: 'Location',
      hideOnMobile: true,
      render: (siteSummary: any) => (
        <span className="text-gray-400 text-sm">
          {siteSummary.location || 'N/A'}
        </span>
      ),
    },
    {
      key: 'total_alarms',
      header: 'Total Alarms',
      render: (siteSummary: any) => (
        <span className="text-white font-semibold text-lg">{siteSummary.total_alarms || 0}</span>
      ),
    },
    {
      key: 'severity',
      header: 'By Severity',
      render: (siteSummary: any) => {
        // Show only the highest severity (Critical > Warning > Info)
        // The backend already sets the severity field to the highest one
        const highestSeverity = siteSummary.severity || 'Info';
        
        // Debug: log the severity value
        if (process.env.NODE_ENV === 'development') {
          console.log(`[Site ${siteSummary.site_id}] Severity:`, highestSeverity, 'All severities:', siteSummary.by_severity);
        }
        
        return (
          <Badge type="severity" value={highestSeverity} size="sm" />
        );
      },
    },
    {
      key: 'timestamp',
      header: 'Latest Alarm',
      hideOnMobile: true,
      render: (siteSummary: any) => (
        <span className="text-gray-400 text-xs">
          {siteSummary.timestamp ? formatRelativeTime(siteSummary.timestamp) : 'N/A'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (siteSummary: any) => {
        const isGenerating = generatingDiagnostics.has(siteSummary.site_id);
        return (
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={async () => {
                setGeneratingDiagnostics(prev => new Set(prev).add(siteSummary.site_id));
                try {
                  const response = await generateSiteDiagnostic(siteSummary.site_id, '-24h');
                  if (response.status === 'success' && response.data) {
                    addToast(`Site diagnostic generated for site ${siteSummary.site_id}`, 'success');
                    // Navigate to diagnostics page with site_id filter
                    window.location.href = `/diagnostics?site_id=${siteSummary.site_id}&highlight=true`;
                  } else {
                    addToast(response.message || 'Failed to generate site diagnostic', 'error');
                  }
                } catch (error: any) {
                  console.error('Error generating site diagnostic:', error);
                  addToast(error?.message || 'Failed to generate site diagnostic', 'error');
                } finally {
                  setGeneratingDiagnostics(prev => {
                    const next = new Set(prev);
                    next.delete(siteSummary.site_id);
                    return next;
                  });
                }
              }}
              disabled={isGenerating}
              className="group hover:bg-purple-600/90 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-200"
            >
              {isGenerating ? (
                <>
                  <LoadingSpinner size="sm" className="mr-1" />
                  Generating...
                </>
              ) : (
                <>
                  <Brain size={14} className="mr-1.5 group-hover:scale-110 transition-transform" />
                  Generate Diagnostic
                </>
              )}
            </Button>
          </div>
        );
      },
    },
  ];


  const handleSearch = (query: string) => {
    setSearchQuery(query);
  };

  // Filter data by search query (for site summaries)
  const filteredData = searchQuery
    ? alarms.filter((item: any) => {
        // For site summaries, search by site_id and site_name
        return (
          (item.site_id && item.site_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
          (item.site_name && item.site_name.toLowerCase().includes(searchQuery.toLowerCase()))
        );
      })
    : alarms;

  // Calculate pagination info with safe defaults
  // If total is not available or 0 but we have alarms, use the actual number of alarms
  // Always prefer actual alarms count if pagination.total is 0 or invalid
  const totalItems = alarms.length > 0 
    ? (pagination.total > 0 ? pagination.total : alarms.length)
    : (pagination.total || 0);
  const itemsPerPage = pagination.limit || 20;
  const currentOffset = pagination.offset || 0;
  const totalPages = totalItems > 0 ? Math.max(1, Math.ceil(totalItems / itemsPerPage)) : 1;
  const currentPage = totalItems > 0 ? Math.max(1, Math.floor(currentOffset / itemsPerPage) + 1) : 1;
  

  // Show loading state during initial data fetch
  if (initialLoading) {
    return <PageLoading message="Loading alarms..." />;
  }

  return (
    <div className="w-full max-w-full min-w-0 space-y-4 sm:space-y-6">
      <div className="flex flex-row items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1">Alarm Management</h1>
          <p className="text-gray-400 text-sm">
            View sites with alarms
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            variant="primary"
            onClick={() => fetchAlarms(filters, pagination.limit, pagination.offset, true)}
            className="text-sm sm:text-base"
          >
            <RefreshCw size={16} className="sm:mr-2" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div className="card">
            <div className="text-sm text-gray-400">Total Alarms</div>
            <div className="text-2xl font-bold text-white">{stats.total}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Critical</div>
            <div className="text-2xl font-bold text-red-400">{stats.by_severity?.Critical || 0}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Warning</div>
            <div className="text-2xl font-bold text-yellow-400">{stats.by_severity?.Warning || 0}</div>
          </div>
          <div className="card">
            <div className="text-sm text-gray-400">Info</div>
            <div className="text-2xl font-bold text-blue-400">{stats.by_severity?.Info || 0}</div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <FilterBar
        onClear={handleClearFilters}
        searchComponent={
          <SearchInput placeholder="Search alarms..." onSearch={handleSearch} />
        }
      >
        <div className="hidden sm:flex items-center gap-x-4 gap-y-2 flex-wrap">
          <FilterSelect
            label="Severity"
            value={selectedSeverity}
            onChange={(v) => {
              setSelectedSeverity(v);
              applyFilters({ severity: v as any });
            }}
            options={Object.values(ALARM_SEVERITY).map((s) => ({ value: s, label: s }))}
            placeholder="All"
          />
          <FilterSelect
            label="Site"
            value={selectedSiteId}
            onChange={(v) => {
              setSelectedSiteId(v);
              applyFilters({ site_id: v || undefined });
            }}
            options={sites.map((s) => ({ value: s.site_id, label: s.site_name || s.site_id }))}
            placeholder="All sites"
          />
          <FilterSelect
            label="Device"
            value={selectedDeviceType}
            onChange={(v) => {
              setSelectedDeviceType(v);
              applyFilters({ device_type: v || undefined });
            }}
            options={Object.values(DEVICE_TYPES).map((t) => ({ value: t, label: t }))}
            placeholder="All types"
          />
          <div className="flex items-center gap-2 shrink-0">
            <DateRangePicker
              label="Date"
              onRangeChange={(start, end) => {
                const next: AlarmFilters = {
                  ...filters,
                  start_time: start || undefined,
                  end_time: end || undefined,
                };
                if (selectedSeverity) next.severity = selectedSeverity as any;
                if (selectedSiteId) next.site_id = selectedSiteId;
                if (selectedDeviceType) next.device_type = selectedDeviceType;
                setLocalFilters(next);
                setFilters(next);
                fetchAlarms(next, pagination.limit, 0, true);
                setPagination(pagination.limit, 0);
              }}
            />
          </div>
        </div>
      </FilterBar>

      {/* Error Message */}
      {error && (
        <div className="card border-red-500 bg-red-500/10">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Site Summary Table */}
      <DataTable
        data={filteredData}
        columns={siteSummaryColumns}
        loading={loading}
        emptyMessage="No sites with alarms found"
      />

      {/* Pagination */}
      {/* Always show pagination if we have alarms, using actual count as fallback */}
      {alarms.length > 0 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalItems > 0 ? totalItems : alarms.length}
          itemsPerPage={itemsPerPage}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
};
