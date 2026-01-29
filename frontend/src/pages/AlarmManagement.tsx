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

  // Initial data fetch on mount - ensure data is loaded immediately
  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      try {
        await Promise.all([
          fetchAlarms(filters, pagination.limit, pagination.offset, true),
          fetchStats(),
        ]);
      } finally {
        setInitialLoading(false);
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

  const handleFilterChange = () => {
    const newFilters: AlarmFilters = {
      ...filters, // Preserve existing filters (like date range)
    };
    if (selectedSeverity) {
      newFilters.severity = selectedSeverity as any;
    } else {
      // Remove severity filter if not selected
      delete newFilters.severity;
    }
    if (selectedSiteId) {
      newFilters.site_id = selectedSiteId;
    } else {
      delete newFilters.site_id;
    }
    if (selectedDeviceType) {
      newFilters.device_type = selectedDeviceType;
    } else {
      delete newFilters.device_type;
    }
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
      render: (siteSummary: any) => (
        <Link
          to={`/datacenter/sites/${siteSummary.site_id}`}
          className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 hover:underline transition-colors"
        >
          <MapPin size={14} className="text-gray-400" />
          <span className="font-mono text-sm font-semibold">{siteSummary.site_id}</span>
        </Link>
      ),
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
            <Link to={`/datacenter/sites/${siteSummary.site_id}`}>
              <Button variant="secondary" size="sm">
                View Site
              </Button>
            </Link>
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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
          <SearchInput
            placeholder="Search alarms by ID, type, or source..."
            onSearch={handleSearch}
          />
        }
      >
          {/* Filter Group - Hidden on mobile */}
          <div className="hidden sm:flex sm:flex-row sm:items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">Filters</span>
            <div className="h-4 w-px bg-gray-700"></div>
            
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Severity</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[140px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
              >
                <option value="">All</option>
                {Object.values(ALARM_SEVERITY).map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </select>
            </div>

            <div className="h-4 w-px bg-gray-700"></div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Site</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[160px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={selectedSiteId}
                onChange={(e) => setSelectedSiteId(e.target.value)}
              >
                <option value="">All Sites</option>
                {sites.map((site) => (
                  <option key={site.site_id} value={site.site_id}>
                    {site.site_name || site.site_id}
                  </option>
                ))}
              </select>
            </div>

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
          </div>

          {/* Date Range Group - Hidden on mobile */}
          <div className="hidden sm:flex sm:flex-row sm:items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">Date</span>
            <div className="h-4 w-px bg-gray-700"></div>
            <div className="flex items-center gap-2">
              <DateRangePicker
            onRangeChange={(start, end) => {
              const newFilters: AlarmFilters = {
                ...filters, // Preserve existing filters
                start_time: start || undefined,
                end_time: end || undefined,
              };
              // Preserve all filters if selected
              if (selectedSeverity) {
                newFilters.severity = selectedSeverity as any;
              } else {
                delete newFilters.severity;
              }
              if (selectedSiteId) {
                newFilters.site_id = selectedSiteId;
              } else {
                delete newFilters.site_id;
              }
              if (selectedDeviceType) {
                newFilters.device_type = selectedDeviceType;
              } else {
                delete newFilters.device_type;
              }
              setLocalFilters(newFilters);
              setFilters(newFilters);
              fetchAlarms(newFilters, pagination.limit, 0, true);
              setPagination(pagination.limit, 0);
            }}
            />
            </div>
          </div>

          <div className="hidden sm:flex items-center gap-2 ml-auto">
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
