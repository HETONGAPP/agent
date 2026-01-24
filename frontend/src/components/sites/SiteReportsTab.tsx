/**
 * Site Reports Tab
 * Displays diagnostic reports for a specific site
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useDiagnostics } from '@/hooks/useDiagnostics';
import { useRealtime } from '@/hooks/useRealtime';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Pagination } from '@/components/ui/Pagination';
import { Badge } from '@/components/ui/Badge';
import { FilterBar } from '@/components/ui/FilterBar';
import { Diagnostic, DiagnosticFilters } from '@/types';
import { formatAbsoluteTime } from '@/utils/date';
import { useToastStore } from '@/store/useToastStore';
import { Eye, Trash2, Filter, FileText } from 'lucide-react';
import { DiagnosticOutput } from '@/components/diagnostics/DiagnosticOutput';
import { DiagnosticDeleteModal } from '@/components/diagnostics/DiagnosticDeleteModal';
import { Modal } from '@/components/ui/Modal';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { useSiteDiagnosticStore } from '@/store/useSiteDiagnosticStore';

interface SiteReportsTabProps {
  siteId: string;
}

export const SiteReportsTab = ({ siteId }: SiteReportsTabProps) => {
  const {
    diagnostics,
    selectedDiagnostic,
    pagination,
    loading,
    error,
    fetchDiagnostics,
    fetchDiagnostic,
    fetchStats,
    deleteDiagnostic,
    setFilters,
    setPagination,
    setSelectedDiagnostic,
  } = useDiagnostics(false); // Disable auto-fetch, we'll fetch manually with site_id filter

  const { addToast } = useToastStore();
  const [filters, setLocalFilters] = useState<DiagnosticFilters>({ site_id: siteId });
  const [selectedRiskLevel, setSelectedRiskLevel] = useState<string>('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [diagnosticToDelete, setDiagnosticToDelete] = useState<Diagnostic | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Monitor diagnostic state to refresh list when diagnostic completes
  const diagnosticsMap = useSiteDiagnosticStore((state) => state.diagnostics);
  const previousGeneratingState = useRef<boolean>(false);

  // Initialize filters with site_id
  useEffect(() => {
    if (!siteId) return;
    const initialFilters = { site_id: siteId };
    setFilters(initialFilters);
    setLocalFilters(initialFilters);
    // Set pagination limit to 15
    setPagination(15, 0);
    fetchDiagnostics(initialFilters, 15, 0);
    fetchStats(undefined, undefined, initialFilters);
  }, [siteId, setFilters, fetchDiagnostics, fetchStats, setPagination]);

  // Monitor diagnostic completion and refresh list
  useEffect(() => {
    if (!siteId) return;
    const diagnosticState = diagnosticsMap[siteId];
    const isCurrentlyGenerating = diagnosticState?.isGenerating || false;
    
    // If diagnostic was generating before but is not now, it means it completed
    if (previousGeneratingState.current && !isCurrentlyGenerating) {
        console.log('[SiteReportsTab] Diagnostic completed, refreshing list');
        // Wait a short moment for the diagnostic to be saved, then refresh
        setTimeout(() => {
          fetchDiagnostics(filters, 15, pagination.offset);
          fetchStats(undefined, undefined, filters);
        }, 1000); // 1 second delay to ensure diagnostic is saved
    }
    
    previousGeneratingState.current = isCurrentlyGenerating;
  }, [siteId, diagnosticsMap, filters, pagination, fetchDiagnostics, fetchStats]);

  // Apply filters
  useEffect(() => {
    if (!siteId) return;
    const newFilters: DiagnosticFilters = { site_id: siteId };
    if (selectedRiskLevel) newFilters.risk_level = selectedRiskLevel as any;
    setLocalFilters(newFilters);
    setFilters(newFilters);
    fetchDiagnostics(newFilters, 15, 0);
    fetchStats(undefined, undefined, newFilters);
  }, [selectedRiskLevel, siteId, setFilters, fetchDiagnostics, fetchStats]);

  // WebSocket for real-time updates
  const wsEvents = useCallback(() => [
    EventType.DIAGNOSTIC_CREATED,
    EventType.STATS_UPDATED,
  ] as EventType[], []);

  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents(),
  });

  // Handle WebSocket events
  useEffect(() => {
    if (!connected) return;

    const unsubscribeDiagnosticCreated = websocketEventManager.subscribe(EventType.DIAGNOSTIC_CREATED, (data: any) => {
      const eventSiteId = data?.site_id;
      
      // Refresh list when diagnostic is created for this site
      if (!eventSiteId || eventSiteId === siteId) {
        console.log('[SiteReportsTab] Diagnostic created, refreshing list');
        // Small delay to ensure diagnostic is saved
        setTimeout(() => {
          fetchDiagnostics(filters, 15, pagination.offset);
          fetchStats(undefined, undefined, filters);
        }, 500);
      }
    });

    const unsubscribeStatsUpdated = websocketEventManager.subscribe(EventType.STATS_UPDATED, (data: any) => {
      const eventSiteId = data?.site_id;
      // Refresh stats when updated
      if (!eventSiteId || eventSiteId === siteId) {
        fetchStats(undefined, undefined, filters);
      }
    });

    return () => {
      unsubscribeDiagnosticCreated();
      unsubscribeStatsUpdated();
    };
  }, [connected, siteId, filters, pagination, fetchDiagnostics, fetchStats]);

  // Real-time updates (fallback polling when WebSocket is not connected)
  useRealtime({
    enabled: true && !loading && !connected,
    interval: 60000, // 60 seconds
    onUpdate: () => {
      if (!loading) {
        fetchDiagnostics(filters, 15, pagination.offset, true);
        fetchStats(undefined, undefined, filters);
      }
    },
  });

  const handlePageChange = (page: number) => {
    const limit = 15;
    const offset = (page - 1) * limit;
    setPagination(limit, offset);
    fetchDiagnostics(filters, limit, offset);
  };

  const columns: Column<Diagnostic>[] = [
    {
      key: 'alarm_id',
      header: 'Diagnostic ID',
      render: (diagnostic) => (
        <span className="font-mono text-gray-300">{diagnostic.alarm_id}</span>
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk Level',
      render: (diagnostic) => (
        <Badge type="risk" value={diagnostic.risk_level} size="sm" />
      ),
    },
    {
      key: 'current_status',
      header: 'Status',
      render: (diagnostic) => (
        <span className="text-gray-300 text-sm truncate max-w-xs block">
          {diagnostic.current_status || 'N/A'}
        </span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Generated At',
      render: (diagnostic) => {
        const absoluteTime = formatAbsoluteTime(diagnostic.timestamp);
        return (
          <span className="text-gray-400 text-xs" title={absoluteTime}>
            {absoluteTime}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (diagnostic) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              fetchDiagnostic(diagnostic.alarm_id);
            }}
            className="p-1.5 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded transition-colors"
            title="View Details"
          >
            <Eye size={16} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setDiagnosticToDelete(diagnostic);
              setShowDeleteModal(true);
            }}
            className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
            title="Remove diagnostic"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ),
    },
  ];

  if (error) {
    return (
      <div className="card p-6 text-center">
        <p className="text-red-400">Error loading diagnostic reports: {error}</p>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700/50">
          <div className="flex items-center gap-3">
            <FileText className="text-blue-400" size={20} />
            <h3 className="text-xl font-semibold text-white">Reports</h3>
            {diagnostics.length > 0 && (
              <Badge type="status" value={`${diagnostics.length} reports`} size="sm" />
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
              <label className="text-sm text-gray-400 whitespace-nowrap">Risk Level:</label>
              <select
                value={selectedRiskLevel}
                onChange={(e) => setSelectedRiskLevel(e.target.value === selectedRiskLevel ? '' : e.target.value)}
                className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
              >
                <option value="">All Risk Levels</option>
                {['High', 'Medium', 'Low'].map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </FilterBar>

        {/* Reports Table */}
        {loading ? (
          <div className="flex items-center justify-center h-[300px]">
            <LoadingSpinner />
          </div>
        ) : diagnostics.length === 0 ? (
          <div className="flex items-center justify-center h-[300px] text-gray-400">
            <div className="text-center">
              <p className="text-lg mb-2">No diagnostic reports found for this site</p>
              <p className="text-sm text-gray-500">Site ID: {siteId}</p>
            </div>
          </div>
        ) : (
          <DataTable
            data={diagnostics as unknown as Record<string, unknown>[]}
            columns={columns as unknown as Column<Record<string, unknown>>[]}
            loading={loading}
            emptyMessage="No diagnostic reports found for this site"
          />
        )}

        {/* Pagination */}
        {pagination.total > 0 && (
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

      {/* Selected Diagnostic Details */}
      {selectedDiagnostic && (
        <Modal
          isOpen={!!selectedDiagnostic}
          onClose={() => setSelectedDiagnostic(null)}
          title=""
          size="xl"
        >
          <DiagnosticOutput
            result={{ report: selectedDiagnostic }}
            onClose={() => setSelectedDiagnostic(null)}
            variant="inline"
          />
        </Modal>
      )}

      {/* Delete Diagnostic Modal */}
      {showDeleteModal && diagnosticToDelete && (
        <DiagnosticDeleteModal
          isOpen={showDeleteModal}
          onClose={() => {
            setShowDeleteModal(false);
            setDiagnosticToDelete(null);
          }}
          onConfirm={async () => {
            if (!diagnosticToDelete) return;
            setIsDeleting(true);
            try {
              const success = await deleteDiagnostic(diagnosticToDelete.alarm_id);
              if (success) {
                addToast({
                  type: 'success',
                  message: 'Diagnostic report removed successfully',
                });
                // Refresh the list
                fetchDiagnostics(filters, 15, pagination.offset);
                fetchStats(undefined, undefined, filters);
                setShowDeleteModal(false);
                setDiagnosticToDelete(null);
              } else {
                addToast({
                  type: 'error',
                  message: 'Failed to remove diagnostic report',
                });
              }
            } catch (error: any) {
              addToast({
                type: 'error',
                message: error?.message || 'Failed to remove diagnostic report',
              });
            } finally {
              setIsDeleting(false);
            }
          }}
          diagnostic={diagnosticToDelete}
          isDeleting={isDeleting}
        />
      )}
    </>
  );
};
