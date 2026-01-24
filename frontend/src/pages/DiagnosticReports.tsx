/**
 * Diagnostic Reports Page
 * Displays diagnostic reports
 */

import { useState, useEffect, useMemo, startTransition, useDeferredValue } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import { useDiagnostics } from '@/hooks/useDiagnostics';
import { useRealtime } from '@/hooks/useRealtime';
import { DataTable, Column } from '@/components/ui/DataTable';
import { FilterBar } from '@/components/ui/FilterBar';
import { SearchInput } from '@/components/ui/SearchInput';
import { DateRangePicker } from '@/components/ui/DateRangePicker';
import { Pagination } from '@/components/ui/Pagination';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Diagnostic, DiagnosticFilters } from '@/types';
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/date';
import { exportDiagnostics } from '@/utils/export';
import { exportMultipleDiagnosticsToPDF } from '@/utils/pdf';
import { useToastStore } from '@/store/useToastStore';
import { Link } from 'react-router-dom';
import { MapPin, Download, Trash2, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { useSiteStore } from '@/store/useSiteStore';
import { DiagnosticOutput } from '@/components/diagnostics/DiagnosticOutput';
import { DiagnosticDeleteModal } from '@/components/diagnostics/DiagnosticDeleteModal';
import { Modal } from '@/components/ui/Modal';

export const DiagnosticReports = () => {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const alarmIdParam = searchParams.get('alarm_id');
  const siteIdParam = searchParams.get('site_id');
  const shouldHighlight = searchParams.get('highlight') === 'true';
  const [highlightedAlarmId, setHighlightedAlarmId] = useState<string | null>(null);
  const [highlightedSiteId, setHighlightedSiteId] = useState<string | null>(null);

  const {
    diagnostics,
    stats,
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
  } = useDiagnostics(false); // Disable auto-fetch, let component control when to fetch

  // Use deferred value for stats to prevent UI flashing during updates
  // This makes stats updates non-blocking and smooth
  const deferredStats = useDeferredValue(stats);

  const { addToast } = useToastStore();
  const { sites, fetchSites } = useSiteStore();
  const [filters, setLocalFilters] = useState<DiagnosticFilters>({
    alarm_id: alarmIdParam || undefined,
    site_id: siteIdParam || undefined,
  });
  const [selectedSiteId, setSelectedSiteId] = useState<string>('');
  const [selectedPriority, setSelectedPriority] = useState<string>('');
  const [prioritySortOrder, setPrioritySortOrder] = useState<'asc' | 'desc' | ''>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [diagnosticToDelete, setDiagnosticToDelete] = useState<Diagnostic | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Fetch sites on mount
  useEffect(() => {
    fetchSites();
  }, [fetchSites]);
  
  // Sync filters with state on mount
  useEffect(() => {
    if (filters.risk_level) {
      setSelectedPriority(filters.risk_level);
    }
    if (filters.site_id) {
      setSelectedSiteId(filters.site_id);
    }
  }, []);

  // Initial data fetch on mount - ensure data is loaded immediately
  useEffect(() => {
    // Only use filters if explicitly navigating from another page (shouldHighlight = true)
    // Otherwise, fetch all diagnostics to show the complete list
    const initialFilters = (shouldHighlight && (alarmIdParam || siteIdParam)) ? filters : {};
    fetchDiagnostics(initialFilters, pagination.limit, pagination.offset);
    // Also update local filters to match
    if (!shouldHighlight || !(alarmIdParam || siteIdParam)) {
      setLocalFilters({});
      setFilters({});
    }
    // Delay stats fetch to avoid blocking the initial render
    // Pass current filters to stats to keep them in sync
    setTimeout(() => {
      fetchStats(undefined, undefined, initialFilters);
    }, 300);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Real-time updates for diagnostics list (only when not loading, with longer interval)
  useRealtime({
    enabled: true && !loading,
    interval: 60000, // 60 seconds to avoid rate limiting
    onUpdate: () => {
      if (!loading) {
        // Use silent mode to prevent UI flashing - keeps table visible during update
        // Only fetch diagnostics list, stats will be updated separately with longer interval
        // This prevents double updates that cause UI stuttering
        fetchDiagnostics(filters, pagination.limit, pagination.offset, true);
      }
    },
  });

  // Fetch stats with 60 second interval and use startTransition to prevent UI blocking
  useRealtime({
    enabled: true && !loading,
    interval: 60000, // 60 seconds
    onUpdate: () => {
      if (!loading) {
        // Use startTransition to mark stats update as non-urgent
        // This prevents UI blocking and flashing
        startTransition(() => {
          fetchStats(undefined, undefined, filters);
        });
      }
    },
  });

  useEffect(() => {
    // Only fetch and show diagnostic if explicitly requested via highlight parameter
    // This prevents auto-opening diagnostic when navigating from alarm page
    if (alarmIdParam && shouldHighlight) {
      fetchDiagnostic(alarmIdParam);
      setHighlightedAlarmId(alarmIdParam);
      // Remove highlight after 3 seconds
      setTimeout(() => {
        setHighlightedAlarmId(null);
        // Remove highlight parameter from URL
        const newParams = new URLSearchParams(searchParams);
        newParams.delete('highlight');
        newParams.delete('alarm_id'); // Also remove alarm_id to prevent auto-opening
        setSearchParams(newParams, { replace: true });
      }, 3000);
    } else if (alarmIdParam && !shouldHighlight) {
      // If alarm_id is in URL but highlight is false, just highlight the row without opening diagnostic
      setHighlightedAlarmId(alarmIdParam);
      // Clean up URL after highlighting
      setTimeout(() => {
        setHighlightedAlarmId(null);
        const newParams = new URLSearchParams(searchParams);
        newParams.delete('alarm_id');
        setSearchParams(newParams, { replace: true });
      }, 3000);
    }
    
    if (siteIdParam && shouldHighlight) {
      setHighlightedSiteId(siteIdParam);
      // Remove highlight after 3 seconds
      setTimeout(() => {
        setHighlightedSiteId(null);
        // Remove highlight parameter from URL
        const newParams = new URLSearchParams(searchParams);
        newParams.delete('highlight');
        newParams.delete('site_id'); // Also remove site_id to prevent auto-opening
        setSearchParams(newParams, { replace: true });
      }, 3000);
    }
  }, [alarmIdParam, siteIdParam, shouldHighlight, fetchDiagnostic, searchParams, setSearchParams]);

  // Clear selected diagnostic when navigating away from diagnostics page
  useEffect(() => {
    // Clear selected diagnostic when route changes away from /diagnostics
    if (location.pathname !== '/diagnostics') {
      setSelectedDiagnostic(null);
    }
  }, [location.pathname, setSelectedDiagnostic]);

  // Clear selected diagnostic on component unmount
  useEffect(() => {
    return () => {
      setSelectedDiagnostic(null);
    };
  }, [setSelectedDiagnostic]);

  const handleFilterChange = () => {
    const newFilters: DiagnosticFilters = {
      ...filters, // Preserve existing filters (like date range and alarm_id)
      alarm_id: alarmIdParam || undefined,
    };
    if (selectedPriority) {
      newFilters.risk_level = selectedPriority as any;
    } else {
      // Remove risk_level filter if not selected
      delete newFilters.risk_level;
    }
    if (selectedSiteId) {
      newFilters.site_id = selectedSiteId;
    } else {
      delete newFilters.site_id;
    }
    if (selectedPriority) {
      newFilters.risk_level = selectedPriority as any;
    } else {
      delete newFilters.risk_level;
    }
    setLocalFilters(newFilters);
    setFilters(newFilters);
    fetchDiagnostics(newFilters, pagination.limit, 0);
    setPagination(pagination.limit, 0);
    // Also update stats with new filters to keep them in sync
    fetchStats(undefined, undefined, newFilters);
  };

  const handleClearFilters = () => {
    setSelectedSiteId('');
    setSelectedPriority('');
    const newFilters: DiagnosticFilters = {};
    setLocalFilters(newFilters);
    setFilters(newFilters);
    fetchDiagnostics(newFilters, pagination.limit, 0);
    setPagination(pagination.limit, 0);
    setSearchParams({});
  };
  
  const handlePageChange = (page: number) => {
    const offset = (page - 1) * pagination.limit;
    setPagination(pagination.limit, offset);
    fetchDiagnostics(filters, pagination.limit, offset);
  };

  const handleExport = () => {
    try {
      exportDiagnostics(diagnostics);
      addToast('Diagnostics exported successfully', 'success');
    } catch (error) {
      addToast('Failed to export diagnostics', 'error');
    }
  };

  const handleExportPDF = async () => {
    try {
      if (filteredDiagnostics.length === 0) {
        addToast('No diagnostics to export', 'warning');
        return;
      }
      await exportMultipleDiagnosticsToPDF(filteredDiagnostics);
      addToast(`Exported ${filteredDiagnostics.length} diagnostic reports as PDF`, 'success');
    } catch (error) {
      console.error('Failed to export PDF:', error);
      addToast('Failed to export PDF', 'error');
    }
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
  };

  // Priority order mapping: High = 3, Medium = 2, Low = 1
  const getPriorityValue = (riskLevel: string): number => {
    switch (riskLevel) {
      case 'High': return 3;
      case 'Medium': return 2;
      case 'Low': return 1;
      default: return 0;
    }
  };

  // Filter diagnostics by search query
  let filteredDiagnostics = searchQuery
    ? diagnostics.filter((diagnostic) =>
        diagnostic.alarm_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (diagnostic.current_status &&
          diagnostic.current_status.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (diagnostic.site_id && diagnostic.site_id.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : diagnostics;

  // Sort by priority if sort order is set
  if (prioritySortOrder) {
    filteredDiagnostics = [...filteredDiagnostics].sort((a, b) => {
      const priorityA = getPriorityValue(a.risk_level);
      const priorityB = getPriorityValue(b.risk_level);
      if (prioritySortOrder === 'asc') {
        // Low to High: Low (1) < Medium (2) < High (3)
        return priorityA - priorityB;
      } else {
        // High to Low: High (3) > Medium (2) > Low (1)
        return priorityB - priorityA;
      }
    });
  }

  const columns: Column<Diagnostic>[] = [
    {
      key: 'alarm_id',
      header: 'Diagnostic ID',
      render: (diagnostic) => (
        <span className="font-mono text-gray-300">
          {diagnostic.alarm_id}
        </span>
      ),
    },
    {
      key: 'site_id',
      header: 'Site',
      render: (diagnostic) => {
        const isHighlighted = highlightedSiteId && diagnostic.site_id === highlightedSiteId;
        return (
          diagnostic.site_id ? (
            <Link
              to={`/datacenter/sites/${diagnostic.site_id}`}
              className={`flex items-center gap-1.5 text-blue-400 hover:text-blue-300 hover:underline transition-colors ${
                isHighlighted ? 'font-bold text-amber-400' : ''
              }`}
            >
              <MapPin size={14} className="text-gray-400" />
              <span className="font-mono text-sm">{diagnostic.site_id}</span>
            </Link>
          ) : (
            <span className="text-gray-500 text-sm flex items-center gap-1.5">
              <MapPin size={14} className="text-gray-600" />
              N/A
            </span>
          )
        );
      },
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
        // Use absolute time format to prevent re-calculation on every render
        // formatRelativeTime recalculates on every render, causing UI stuttering
        // Absolute time is static and won't change, preventing unnecessary re-renders
        const absoluteTime = formatAbsoluteTime(diagnostic.timestamp);
        const relativeTime = formatRelativeTime(diagnostic.timestamp);
        return (
          <span 
            className="text-gray-400 text-xs" 
            title={relativeTime}
          >
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
          <Button
            variant="secondary"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              fetchDiagnostic(diagnostic.alarm_id);
            }}
          >
            View Details
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setDiagnosticToDelete(diagnostic);
              setShowDeleteModal(true);
            }}
          >
            <Trash2 size={16} className="mr-1" />
            Remove
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">Diagnostic Reports</h1>
          <p className="text-gray-400 text-sm">AI-powered diagnostic analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="secondary" 
            onClick={handleExportPDF} 
            disabled={filteredDiagnostics.length === 0}
            className="flex items-center gap-2"
          >
            <Download size={16} />
            Export PDF
          </Button>
          <Button variant="secondary" onClick={handleExport} disabled={diagnostics.length === 0}>
            Export CSV
          </Button>
          <Button variant="primary" onClick={() => {
            fetchDiagnostics(filters, pagination.limit, pagination.offset);
            fetchStats(undefined, undefined, filters); // Also refresh stats on manual refresh
          }}>
            Refresh
          </Button>
        </div>
      </div>

      {/* Statistics - Using deferred value and smooth transitions to prevent UI flashing */}
      {useMemo(() => {
        if (!deferredStats) return null;
        const isPending = deferredStats !== stats;
        
        // Normalize risk level keys to handle case sensitivity issues
        const byRiskLevel = deferredStats.by_risk_level || {};
        const high = byRiskLevel.High || byRiskLevel.high || 0;
        const medium = byRiskLevel.Medium || byRiskLevel.medium || 0;
        const low = byRiskLevel.Low || byRiskLevel.low || 0;
        
        // Debug: Log stats and diagnostics to identify mismatch
        if (diagnostics.length > 0 && deferredStats.total > 0) {
          const diagnosticsByRisk = diagnostics.reduce((acc, d) => {
            const level = d.risk_level || 'Unknown';
            acc[level] = (acc[level] || 0) + 1;
            return acc;
          }, {} as Record<string, number>);
          
          // Only log if there's a mismatch
          if (high !== (diagnosticsByRisk.High || diagnosticsByRisk.high || 0) ||
              medium !== (diagnosticsByRisk.Medium || diagnosticsByRisk.medium || 0) ||
              low !== (diagnosticsByRisk.Low || diagnosticsByRisk.low || 0)) {
            console.log('[DiagnosticReports] Stats mismatch detected:', {
              stats: { high, medium, low, total: deferredStats.total },
              diagnostics: diagnosticsByRisk,
              diagnosticsCount: diagnostics.length,
              byRiskLevel,
            });
          }
        }
        
        return (
          <div className={`grid grid-cols-1 md:grid-cols-4 gap-4 transition-opacity duration-300 ${isPending ? 'opacity-60' : 'opacity-100'}`}>
            <div className="card transition-all duration-200">
              <div className="text-sm text-gray-400">Total Reports</div>
              <div className="text-2xl font-bold text-white transition-all duration-200">{deferredStats.total}</div>
            </div>
            <div className="card transition-all duration-200">
              <div className="text-sm text-gray-400">High Risk</div>
              <div className="text-2xl font-bold text-red-400 transition-all duration-200">{high}</div>
            </div>
            <div className="card transition-all duration-200">
              <div className="text-sm text-gray-400">Medium Risk</div>
              <div className="text-2xl font-bold text-yellow-400 transition-all duration-200">{medium}</div>
            </div>
            <div className="card transition-all duration-200">
              <div className="text-sm text-gray-400">Low Risk</div>
              <div className="text-2xl font-bold text-green-400 transition-all duration-200">{low}</div>
            </div>
          </div>
        );
      }, [deferredStats, stats, diagnostics])}

      {/* Search and Filters */}
      <FilterBar 
        onClear={handleClearFilters}
        searchComponent={
          <SearchInput
            placeholder="Search diagnostics by diagnostic ID or status..."
            onSearch={handleSearch}
          />
        }
      >
          {alarmIdParam && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/30 rounded-md whitespace-nowrap flex-shrink-0">
              <span className="text-xs font-medium text-blue-300">Diagnostic ID:</span>
              <span className="font-mono text-blue-400 text-sm font-semibold">{alarmIdParam}</span>
            </div>
          )}
          
          {/* Filter Group - Fixed width to prevent shifting */}
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg whitespace-nowrap flex-shrink-0">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Filters</span>
            <div className="h-4 w-px bg-gray-700"></div>
            
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Site</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[140px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
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
              <label className="text-xs text-gray-400 whitespace-nowrap font-medium">Priority</label>
              <select
                className="px-2.5 py-1.5 bg-gray-900/80 border border-gray-700 rounded-md text-white text-sm min-w-[120px] hover:border-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                value={selectedPriority}
                onChange={(e) => setSelectedPriority(e.target.value)}
              >
                <option value="">All</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>
          </div>

          {/* Sort Group - Fixed width to prevent shifting */}
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg whitespace-nowrap flex-shrink-0">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider w-10 flex-shrink-0">Sort</span>
            <div className="h-4 w-px bg-gray-700 flex-shrink-0"></div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <Button
                variant={prioritySortOrder === 'asc' ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => {
                  if (prioritySortOrder === 'asc') {
                    setPrioritySortOrder('');
                  } else {
                    setPrioritySortOrder('asc');
                  }
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium w-[110px] flex-shrink-0 box-border"
                style={{ 
                  minWidth: '110px', 
                  maxWidth: '110px',
                  borderWidth: prioritySortOrder === 'asc' ? '1px' : '1px',
                  borderStyle: 'solid',
                  borderColor: prioritySortOrder === 'asc' ? 'transparent' : 'rgb(75, 85, 99)',
                  boxShadow: prioritySortOrder === 'asc' ? '0 10px 15px -3px rgba(59, 130, 246, 0.2), 0 4px 6px -2px rgba(59, 130, 246, 0.2)' : 'none'
                }}
                title="Sort: Low to High"
              >
                <ArrowUp size={12} />
                Low to High
              </Button>
              <Button
                variant={prioritySortOrder === 'desc' ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => {
                  if (prioritySortOrder === 'desc') {
                    setPrioritySortOrder('');
                  } else {
                    setPrioritySortOrder('desc');
                  }
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium w-[110px] flex-shrink-0 box-border"
                style={{ 
                  minWidth: '110px', 
                  maxWidth: '110px',
                  borderWidth: prioritySortOrder === 'desc' ? '1px' : '1px',
                  borderStyle: 'solid',
                  borderColor: prioritySortOrder === 'desc' ? 'transparent' : 'rgb(75, 85, 99)',
                  boxShadow: prioritySortOrder === 'desc' ? '0 10px 15px -3px rgba(59, 130, 246, 0.2), 0 4px 6px -2px rgba(59, 130, 246, 0.2)' : 'none'
                }}
                title="Sort: High to Low"
              >
                <ArrowDown size={12} />
                High to Low
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPrioritySortOrder('')}
                className={`w-8 h-8 flex items-center justify-center flex-shrink-0 box-border ${prioritySortOrder ? 'text-white' : 'text-gray-400 hover:text-white'}`}
                style={{ 
                  minWidth: '32px', 
                  maxWidth: '32px',
                  minHeight: '32px',
                  maxHeight: '32px',
                  padding: '0'
                }}
                title="Clear sort"
                disabled={!prioritySortOrder}
              >
                <ArrowUpDown size={12} />
              </Button>
            </div>
          </div>

          {/* Date Range Group - Fixed width to prevent shifting */}
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-800/50 border border-gray-700/50 rounded-lg whitespace-nowrap flex-shrink-0">
            <DateRangePicker
            onRangeChange={(start, end) => {
              const newFilters: DiagnosticFilters = {
                ...filters, // Preserve existing filters
                alarm_id: alarmIdParam || undefined,
                start_time: start || undefined,
                end_time: end || undefined,
              };
              // Preserve all filters if selected
              if (selectedPriority) {
                newFilters.risk_level = selectedPriority as any;
              } else {
                delete newFilters.risk_level;
              }
              if (selectedSiteId) {
                newFilters.site_id = selectedSiteId;
              } else {
                delete newFilters.site_id;
              }
              if (selectedPriority) {
                newFilters.risk_level = selectedPriority as any;
              } else {
                delete newFilters.risk_level;
              }
              setLocalFilters(newFilters);
              setFilters(newFilters);
              fetchDiagnostics(newFilters, pagination.limit, 0);
              setPagination(pagination.limit, 0);
              // Also update stats with new filters to keep them in sync
              fetchStats(undefined, undefined, newFilters);
            }}
            />
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

      {/* Diagnostic Table */}
      <DataTable
        data={filteredDiagnostics}
        columns={columns}
        loading={loading}
        emptyMessage={
          diagnostics.length === 0 && !loading
            ? `No diagnostic reports found${filters.alarm_id || filters.site_id ? ' matching the current filters' : ''}. ${stats?.total ? `Total reports in system: ${stats.total}` : ''}`
            : 'No diagnostic reports found'
        }
        highlightedRowKey="alarm_id"
        highlightedRowValue={highlightedAlarmId}
      />

      {/* Pagination */}
      {Math.ceil(pagination.total / pagination.limit) > 1 && (
        <Pagination
          currentPage={Math.floor(pagination.offset / pagination.limit) + 1}
          totalPages={Math.ceil(pagination.total / pagination.limit)}
          totalItems={pagination.total}
          itemsPerPage={pagination.limit}
          onPageChange={handlePageChange}
        />
      )}

      {/* Selected Diagnostic Details - Using new professional component */}
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
                fetchDiagnostics(filters, pagination.limit, pagination.offset);
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
    </div>
  );
};
