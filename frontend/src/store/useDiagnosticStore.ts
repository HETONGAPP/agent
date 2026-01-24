/**
 * Diagnostic Store
 * Zustand store for diagnostic reports management
 */

import { create } from 'zustand';
import { Diagnostic, DiagnosticStats, DiagnosticFilters, ApiResponse } from '@/types';
import { getDiagnostics, getDiagnostic, getDiagnosticStats, deleteDiagnostic as deleteDiagnosticAPI } from '@/api/diagnostics';

interface DiagnosticStore {
  // State
  diagnostics: Diagnostic[];
  selectedDiagnostic: Diagnostic | null;
  stats: DiagnosticStats | null;
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
  loading: boolean;
  error: string | null;
  filters: DiagnosticFilters | undefined;
  // Cache for stats to avoid duplicate fetches
  statsCache: {
    key: string;
    stats: DiagnosticStats;
    timestamp: number;
  } | null;

  // Actions
  fetchDiagnostics: (filters?: DiagnosticFilters, limit?: number, offset?: number, silent?: boolean) => Promise<void>;
  fetchDiagnostic: (alarmId: string) => Promise<void>;
  fetchStats: (startTime?: string, endTime?: string, filters?: DiagnosticFilters, forceUpdate?: boolean) => Promise<void>;
  deleteDiagnostic: (alarmId: string) => Promise<boolean>;
  setFilters: (filters: DiagnosticFilters | undefined) => void;
  setPagination: (limit: number, offset: number) => void;
  setSelectedDiagnostic: (diagnostic: Diagnostic | null) => void;
  clearError: () => void;
}

export const useDiagnosticStore = create<DiagnosticStore>((set, get) => ({
  // Initial state
  diagnostics: [],
  selectedDiagnostic: null,
  stats: null,
  pagination: {
    limit: 20,
    offset: 0,
    total: 0,
  },
  loading: false,
  error: null,
  filters: undefined,
  statsCache: null,

  // Fetch diagnostics list
  fetchDiagnostics: async (filters, limit = 20, offset = 0, silent = false) => {
    // Only set loading state if not a silent update (silent updates are for real-time refreshes)
    // This prevents UI flashing when data updates in the background
    if (!silent) {
      set({ loading: true, error: null });
    }
    try {
      const response: ApiResponse<{ diagnostics: Diagnostic[]; total: number; limit: number; offset: number }> =
        await getDiagnostics(filters, limit, offset);
      
      if (response.status === 'success' && response.data) {
        set({
          diagnostics: response.data.diagnostics,
          pagination: {
            limit: response.data.limit,
            offset: response.data.offset,
            total: response.data.total,
          },
          loading: false,
        });
      } else {
        set({
          error: response.message || 'Failed to fetch diagnostics',
          loading: false,
        });
      }
    } catch (error: any) {
      set({
        error: error.message || 'Failed to fetch diagnostics',
        loading: false,
      });
    }
  },

  // Fetch single diagnostic
  // Don't set loading state to prevent list refresh/flashing when viewing details
  fetchDiagnostic: async (alarmId: string) => {
    // Only set error to null, don't set loading to prevent UI flashing
    // The list should remain visible while fetching diagnostic details
    set({ error: null });
    try {
      const response: ApiResponse<Diagnostic> = await getDiagnostic(alarmId);
      
      if (response.status === 'success' && response.data) {
        set({
          selectedDiagnostic: response.data,
        });
      } else {
        set({
          error: response.message || 'Failed to fetch diagnostic',
        });
      }
    } catch (error: any) {
      set({
        error: error.message || 'Failed to fetch diagnostic',
      });
    }
  },

  // Fetch statistics with caching to avoid duplicate fetches
  fetchStats: async (startTime?: string, endTime?: string, filters?: DiagnosticFilters, forceUpdate?: boolean) => {
    // Generate cache key from parameters
    const cacheKey = JSON.stringify({ startTime, endTime, filters });
    const cache = get().statsCache;
    const CACHE_TTL = 5000; // 5 seconds cache
    
    // Check cache if not forcing update
    if (!forceUpdate && cache && cache.key === cacheKey) {
      const age = Date.now() - cache.timestamp;
      if (age < CACHE_TTL) {
        // Use cached stats if available and fresh
        set({ stats: cache.stats });
        return;
      }
    }
    
    try {
      const response: ApiResponse<DiagnosticStats> = await getDiagnosticStats(startTime, endTime, filters);
      
      if (response.status === 'success' && response.data) {
        const currentStats = get().stats;
        const newStats = response.data;
        
        // Update cache
        set({
          statsCache: {
            key: cacheKey,
            stats: newStats,
            timestamp: Date.now(),
          },
        });
        
        // If forceUpdate is true, always update regardless of comparison
        // This is useful after deletions to ensure stats are refreshed from server
        if (forceUpdate) {
          set({ stats: newStats });
          return;
        }
        
        // Only update if stats actually changed to prevent unnecessary re-renders
        // Compare stats to avoid unnecessary updates
        // Deep comparison to prevent updates when data hasn't actually changed
        const statsChanged = !currentStats || 
            currentStats.total !== newStats.total ||
            (currentStats.by_risk_level?.High || 0) !== (newStats.by_risk_level?.High || 0) ||
            (currentStats.by_risk_level?.Medium || 0) !== (newStats.by_risk_level?.Medium || 0) ||
            (currentStats.by_risk_level?.Low || 0) !== (newStats.by_risk_level?.Low || 0);
        
        if (statsChanged) {
          // Use a small delay to batch the update and make it smoother
          // This prevents UI flashing by allowing React to batch the state update
          setTimeout(() => {
            set({ stats: newStats });
          }, 0);
        } else {
          // Stats haven't changed, skip update to prevent re-render
          return;
        }
      }
    } catch (error: any) {
      // Silently handle request cancellation errors (normal when component unmounts)
      if (error?.message?.includes('aborted') || error?.code === 'ERR_CANCELED' || error?.name === 'AbortError') {
        return; // Silently ignore cancelled requests
      }
      console.error('Failed to fetch diagnostic stats:', error);
      // Don't set error state for stats, just log it
    }
  },

  // Set filters
  setFilters: (filters) => {
    set({ filters });
  },

  // Set pagination
  setPagination: (limit, offset) => {
    set({
      pagination: {
        ...get().pagination,
        limit,
        offset,
      },
    });
  },

  // Set selected diagnostic
  setSelectedDiagnostic: (diagnostic) => {
    set({ selectedDiagnostic: diagnostic });
  },

  // Delete diagnostic
  deleteDiagnostic: async (alarmId: string) => {
    set({ loading: true, error: null });
    try {
      const response: ApiResponse<void> = await deleteDiagnosticAPI(alarmId);
      
      if (response.status === 'success') {
        // Remove from local state
        const currentDiagnostics = get().diagnostics;
        const deletedDiagnostic = currentDiagnostics.find(d => d.alarm_id === alarmId);
        const updatedDiagnostics = currentDiagnostics.filter(d => d.alarm_id !== alarmId);
        
        // Update pagination total
        const currentPagination = get().pagination;
        const updatedPagination = {
          ...currentPagination,
          total: Math.max(0, currentPagination.total - 1),
        };
        
        // Update stats locally to keep UI in sync immediately
        const currentStats = get().stats;
        if (currentStats) {
          let updatedStats = { ...currentStats };
          
          if (deletedDiagnostic) {
            // If we found the deleted diagnostic, update stats based on its risk level
            const riskLevel = deletedDiagnostic.risk_level;
            updatedStats = {
              ...currentStats,
              total: Math.max(0, currentStats.total - 1),
              by_risk_level: {
                ...currentStats.by_risk_level,
                High: Math.max(0, (currentStats.by_risk_level?.High || 0) - (riskLevel === 'High' ? 1 : 0)),
                Medium: Math.max(0, (currentStats.by_risk_level?.Medium || 0) - (riskLevel === 'Medium' ? 1 : 0)),
                Low: Math.max(0, (currentStats.by_risk_level?.Low || 0) - (riskLevel === 'Low' ? 1 : 0)),
              },
            };
          } else {
            // If deleted diagnostic not found in current list, recalculate from remaining diagnostics
            // This handles cases where the deleted diagnostic was filtered out
            const riskLevelCounts = updatedDiagnostics.reduce((acc, d) => {
              const level = d.risk_level;
              if (level) {
                acc[level] = (acc[level] || 0) + 1;
              }
              return acc;
            }, {} as Record<string, number>);
            
            updatedStats = {
              total: updatedDiagnostics.length,
              by_risk_level: {
                High: riskLevelCounts.High || riskLevelCounts.high || 0,
                Medium: riskLevelCounts.Medium || riskLevelCounts.medium || 0,
                Low: riskLevelCounts.Low || riskLevelCounts.low || 0,
              },
            };
          }
          
          // Ensure all risk levels are present even if 0
          if (!updatedStats.by_risk_level.High && updatedStats.by_risk_level.High !== 0) {
            updatedStats.by_risk_level.High = 0;
          }
          if (!updatedStats.by_risk_level.Medium && updatedStats.by_risk_level.Medium !== 0) {
            updatedStats.by_risk_level.Medium = 0;
          }
          if (!updatedStats.by_risk_level.Low && updatedStats.by_risk_level.Low !== 0) {
            updatedStats.by_risk_level.Low = 0;
          }
          
          set({
            diagnostics: updatedDiagnostics,
            pagination: updatedPagination,
            stats: updatedStats,
            loading: false,
          });
        } else {
          set({
            diagnostics: updatedDiagnostics,
            pagination: updatedPagination,
            loading: false,
          });
        }
        
        // Clear selected diagnostic if it was deleted
        const selectedDiagnostic = get().selectedDiagnostic;
        if (selectedDiagnostic && selectedDiagnostic.alarm_id === alarmId) {
          set({ selectedDiagnostic: null });
        }
        
        return true;
      } else {
        set({
          error: response.message || 'Failed to delete diagnostic',
          loading: false,
        });
        return false;
      }
    } catch (error: any) {
      set({
        error: error.message || 'Failed to delete diagnostic',
        loading: false,
      });
      return false;
    }
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
