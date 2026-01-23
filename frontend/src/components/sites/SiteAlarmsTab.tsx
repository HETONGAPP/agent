/**
 * Site Alarms Tab
 * Displays all alarms for a specific site (including device-level alarms)
 */

import { useState, useEffect, useCallback } from 'react';
import { useAlarms } from '@/hooks/useAlarms';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { DataTable, Column } from '@/components/ui/DataTable';
import { SearchInput } from '@/components/ui/SearchInput';
import { Pagination } from '@/components/ui/Pagination';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alarm, AlarmFilters } from '@/types';
import { ALARM_SEVERITY } from '@/config/constants';
import { formatRelativeTime } from '@/utils/date';
import { exportAlarms } from '@/utils/export';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin, Brain } from 'lucide-react';
import { generateAlarmDiagnostic } from '@/api/diagnostics';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { websocketEventManager } from '@/services/websocketEventManager';

interface SiteAlarmsTabProps {
  siteId: string;
}

export const SiteAlarmsTab = ({ siteId }: SiteAlarmsTabProps) => {
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
  } = useAlarms(false, { site_id: siteId }); // Don't auto-fetch, we'll fetch manually with site_id filter

  const { addToast } = useToastStore();
  const [filters, setLocalFilters] = useState<AlarmFilters>({ site_id: siteId });
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [generatingDiagnostics, setGeneratingDiagnostics] = useState<Set<string>>(new Set());
  
  // WebSocket for real-time updates
  const wsEvents = useCallback(() => [
    EventType.ALARM_CREATED,
    EventType.ALARM_UPDATED,
    EventType.STATS_UPDATED,
  ] as EventType[], []);

  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents()
  });

  // Initialize filters with site_id
  useEffect(() => {
    if (!siteId) return;
    const initialFilters = { site_id: siteId };
    setFilters(initialFilters);
    setLocalFilters(initialFilters);
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(initialFilters, pagination.limit, 0, false);
    fetchStats();
  }, [siteId, setFilters, fetchAlarms, fetchStats, pagination.limit]);

  // Handle WebSocket events
  useEffect(() => {
    if (!connected) return;

    const unsubscribe = websocketEventManager.subscribe((event) => {
      const eventSiteId = event.data?.site_id;
      const isRuleUpdate = event.data?.reason === 'rule_updated' || event.data?.reason === 'rule_added' || event.data?.reason === 'rule_deleted';
      
      if (event.type === EventType.ALARM_CREATED || event.type === EventType.ALARM_UPDATED) {
        // Refresh alarms if they belong to this site or if it's a rule update for this site
        const alarm = event.data;
        const alarmSiteId = alarm?.site_id;
        
        if (alarmSiteId === siteId || (isRuleUpdate && eventSiteId === siteId)) {
          // When querying a specific site, don't use aggregate_by_site (we want all alarms)
          fetchAlarms(filters, pagination.limit, pagination.offset, false);
          fetchStats();
        }
      } else if (event.type === EventType.STATS_UPDATED) {
        // Refresh stats and alarms if the update is for this site
        if (!eventSiteId || eventSiteId === siteId) {
          fetchStats();
          // Also refresh alarms if it's a rule-related update for this site
          if (isRuleUpdate && eventSiteId === siteId) {
            fetchAlarms(filters, pagination.limit, pagination.offset, false);
          }
        }
      }
    });

    return unsubscribe;
  }, [connected, siteId, filters, pagination, fetchAlarms, fetchStats]);

  // Apply filters
  useEffect(() => {
    if (!siteId) return;
    const newFilters: AlarmFilters = { site_id: siteId };
    if (selectedSeverity) newFilters.severity = selectedSeverity as any;
    if (searchQuery) {
      // Search in alarm_id, alarm_type, or source
      newFilters.alarm_type = searchQuery;
    }
    setLocalFilters(newFilters);
    setFilters(newFilters);
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(newFilters, pagination.limit, 0, false);
  }, [selectedSeverity, searchQuery, siteId, setFilters, fetchAlarms, pagination.limit]);

  const handleSeverityFilter = (severity: string) => {
    setSelectedSeverity(severity === selectedSeverity ? '' : severity);
  };

  const handlePageChange = (page: number) => {
    const offset = (page - 1) * pagination.limit;
    setPagination({ ...pagination, offset });
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(filters, pagination.limit, offset, false);
  };

  const handleGenerateDiagnostic = async (alarmId: string) => {
    setGeneratingDiagnostics(prev => new Set(prev).add(alarmId));
    try {
      const response = await generateAlarmDiagnostic(alarmId);
      if (response.status === 'success') {
        addToast('Diagnostic generated successfully', 'success');
        // Refresh alarms to get updated diagnostic
        fetchAlarms(filters, pagination.limit, pagination.offset, false);
      } else {
        addToast(response.message || 'Failed to generate diagnostic', 'error');
      }
    } catch (error: any) {
      console.error('Error generating diagnostic:', error);
      addToast(error?.message || 'Failed to generate diagnostic', 'error');
    } finally {
      setGeneratingDiagnostics(prev => {
        const next = new Set(prev);
        next.delete(alarmId);
        return next;
      });
    }
  };

  const columns: Column<Alarm>[] = [
    {
      key: 'alarm_id',
      header: 'Alarm ID',
      render: (alarm) => (
        <span className="font-mono text-blue-400">{alarm.alarm_id}</span>
      ),
    },
    {
      key: 'alarm_type',
      header: 'Type',
      render: (alarm) => (
        <span className="text-gray-300">{alarm.alarm_type}</span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (alarm) => (
        <Badge type="severity" value={alarm.severity} size="sm" />
      ),
    },
    {
      key: 'alarm_level',
      header: 'Level',
      render: (alarm) => {
        const level = (alarm as any).alarm_level || 'device_level';
        const levelMap: Record<string, { label: string; color: string }> = {
          system_level: { label: 'System', color: 'purple' },
          site_level: { label: 'Site', color: 'blue' },
          device_level: { label: 'Device', color: 'gray' },
        };
        const levelInfo = levelMap[level] || levelMap.device_level;
        return (
          <Badge
            type="custom"
            value={levelInfo.label}
            className={`bg-${levelInfo.color}-500/10 text-${levelInfo.color}-400 border-${levelInfo.color}-500/20`}
            size="sm"
          />
        );
      },
    },
    {
      key: 'source',
      header: 'Source',
      render: (alarm) => (
        <span className="text-gray-300">{alarm.source}</span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Timestamp',
      render: (alarm) => (
        <span className="text-gray-400 text-xs">
          {formatRelativeTime(alarm.timestamp)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (alarm) => (
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleGenerateDiagnostic(alarm.alarm_id)}
            disabled={generatingDiagnostics.has(alarm.alarm_id)}
            className="text-xs"
          >
            {generatingDiagnostics.has(alarm.alarm_id) ? (
              <>
                <LoadingSpinner size="xs" className="mr-1" />
                Generating...
              </>
            ) : (
              <>
                <Brain size={12} className="mr-1" />
                Diagnostic
              </>
            )}
          </Button>
        </div>
      ),
    },
  ];

  if (error) {
    return (
      <div className="card p-6 text-center">
        <p className="text-red-400">Error loading alarms: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <SearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search alarms..."
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(ALARM_SEVERITY).map(([key, value]) => (
              <Button
                key={key}
                variant={selectedSeverity === value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => handleSeverityFilter(value)}
              >
                {key}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card p-4">
            <div className="text-sm text-gray-400 mb-1">Total Alarms</div>
            <div className="text-2xl font-bold text-white">{stats.total}</div>
          </div>
          <div className="card p-4">
            <div className="text-sm text-gray-400 mb-1">Critical</div>
            <div className="text-2xl font-bold text-red-400">{stats.by_severity?.Critical || 0}</div>
          </div>
          <div className="card p-4">
            <div className="text-sm text-gray-400 mb-1">Warning</div>
            <div className="text-2xl font-bold text-yellow-400">{stats.by_severity?.Warning || 0}</div>
          </div>
          <div className="card p-4">
            <div className="text-sm text-gray-400 mb-1">Info</div>
            <div className="text-2xl font-bold text-blue-400">{stats.by_severity?.Info || 0}</div>
          </div>
        </div>
      )}

      {/* Alarms Table */}
      <div className="card">
        {loading ? (
          <div className="flex items-center justify-center h-[300px]">
            <LoadingSpinner />
          </div>
        ) : alarms.length === 0 ? (
          <div className="flex items-center justify-center h-[300px] text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-2">No alarms found for this site</p>
              <p className="text-sm text-gray-500">Site ID: {siteId}</p>
            </div>
          </div>
        ) : (
          <DataTable
            data={alarms}
            columns={columns}
            loading={loading}
            emptyMessage="No alarms found for this site"
          />
        )}
      </div>

      {/* Pagination */}
      {pagination.total > 0 && (
        <Pagination
          currentPage={Math.floor(pagination.offset / pagination.limit) + 1}
          totalPages={Math.ceil(pagination.total / pagination.limit)}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
};

