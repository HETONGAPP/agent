/**
 * Site Alarms Tab
 * Displays all alarms for a specific site (including device-level alarms)
 */

import { useState, useEffect, useCallback } from 'react';
import { useAlarms } from '@/hooks/useAlarms';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { FilterBar } from '@/components/ui/FilterBar';
import { Alarm, AlarmFilters } from '@/types';
import { ALARM_SEVERITY } from '@/config/constants';
import { formatRelativeTime } from '@/utils/date';
import { exportAlarms } from '@/utils/export';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin, Brain, Filter, AlertTriangle } from 'lucide-react';
import { generateAlarmDiagnostic } from '@/api/diagnostics';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { websocketEventManager } from '@/services/websocketEventManager';

interface SiteAlarmsTabProps {
  siteId: string;
}

export const SiteAlarmsTab = ({ siteId }: SiteAlarmsTabProps) => {
  const {
    alarms,
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
    // Set pagination limit to 15
    setPagination(15, 0);
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(initialFilters, 15, 0, false);
    fetchStats();
  }, [siteId, setFilters, fetchAlarms, fetchStats, setPagination]);

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
          fetchAlarms(filters, 15, pagination.offset, false);
          fetchStats();
        }
      } else if (event.type === EventType.STATS_UPDATED) {
        // Refresh stats and alarms if the update is for this site
        if (!eventSiteId || eventSiteId === siteId) {
          fetchStats();
          // Also refresh alarms if it's a rule-related update for this site
          if (isRuleUpdate && eventSiteId === siteId) {
            fetchAlarms(filters, 15, pagination.offset, false);
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
    setLocalFilters(newFilters);
    setFilters(newFilters);
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(newFilters, 15, 0, false);
  }, [selectedSeverity, siteId, setFilters, fetchAlarms]);

  const handleSeverityFilter = (severity: string) => {
    setSelectedSeverity(severity);
  };

  const handlePageChange = (page: number) => {
    const limit = 15;
    const offset = (page - 1) * limit;
    setPagination(limit, offset);
    // When querying a specific site, don't use aggregate_by_site (we want all alarms)
    fetchAlarms(filters, limit, offset, false);
  };

  const handleGenerateDiagnostic = async (alarmId: string) => {
    setGeneratingDiagnostics(prev => new Set(prev).add(alarmId));
    try {
      const response = await generateAlarmDiagnostic(alarmId);
      if (response.status === 'success') {
        addToast('Diagnostic generated successfully', 'success');
        // Refresh alarms to get updated diagnostic
        fetchAlarms(filters, 15, pagination.offset, false);
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
        const levelMap: Record<string, { label: string; colorClass: string }> = {
          system_level: { label: 'System', colorClass: 'bg-purple-500/20 text-purple-400 border-purple-500/50' },
          site_level: { label: 'Site', colorClass: 'bg-blue-500/20 text-blue-400 border-blue-500/50' },
          device_level: { label: 'Device', colorClass: 'bg-gray-500/20 text-gray-400 border-gray-500/50' },
        };
        const levelInfo = levelMap[level] || levelMap.device_level;
        return (
          <span className={`badge border px-2 py-0.5 text-xs ${levelInfo.colorClass}`}>
            {levelInfo.label}
          </span>
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
    <div className="card">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700/50">
        <div className="flex items-center gap-3">
          <AlertTriangle className="text-red-400" size={20} />
          <h3 className="text-xl font-semibold text-white">Alarms</h3>
          {alarms.length > 0 && (
            <Badge type="status" value={`${alarms.length} alarms`} size="sm" />
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <FilterBar
        showClear={false}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-gray-400" />
            <label className="text-sm text-gray-400 whitespace-nowrap">Severity:</label>
            <select
              value={selectedSeverity}
              onChange={(e) => handleSeverityFilter(e.target.value)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
            >
              <option value="">All Severities</option>
              {Object.entries(ALARM_SEVERITY).map(([key, value]) => (
                <option key={key} value={value}>
                  {key}
                </option>
              ))}
            </select>
          </div>
        </div>
      </FilterBar>

      {/* Alarms Table */}
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

      {/* Pagination */}
      {!loading && alarms.length > 0 && pagination.total > 0 && (
        <div className="mt-4">
          <Pagination
            currentPage={Math.floor(pagination.offset / 15) + 1}
            totalPages={Math.ceil(pagination.total / 15)}
            totalItems={pagination.total}
            itemsPerPage={15}
            onPageChange={handlePageChange}
          />
        </div>
      )}
    </div>
  );
};

