/**
 * Alarm Store
 * Zustand store for alarm state management
 */

import { create } from 'zustand';
import { Alarm, AlarmStats, AlarmFilters } from '@/types';
import { getAlarms, getAlarm, getAlarmStats } from '@/api/alarms';
import { dataService } from '@/services/dataService';

interface AlarmState {
  alarms: Alarm[];
  selectedAlarm: Alarm | null;
  stats: AlarmStats | null;
  filters: AlarmFilters;
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchAlarms: (filters?: AlarmFilters, limit?: number, offset?: number, aggregateBySite?: boolean) => Promise<void>;
  fetchAlarm: (alarmId: string) => Promise<void>;
  fetchStats: (startTime?: string, endTime?: string) => Promise<void>;
  setFilters: (filters: AlarmFilters) => void;
  setPagination: (limit: number, offset: number) => void;
  setSelectedAlarm: (alarm: Alarm | null) => void;
  clearError: () => void;
}

/**
 * Deduplicate alarms by site_id when aggregateBySite is true
 * Returns a new array with only unique site_ids (first occurrence wins)
 */
function deduplicateSiteAlarms(alarms: any[]): any[] {
  const siteMap = new Map<string, any>();
  
  for (const alarm of alarms) {
    const siteId = String(alarm.site_id || '');
    if (!siteId) {
      // No site_id, include it
      continue;
    }
    
    // Only keep the first occurrence
    if (!siteMap.has(siteId)) {
      siteMap.set(siteId, alarm);
    }
  }
  
  // Convert map values back to array
  const uniqueAlarms = Array.from(siteMap.values());
  
  // Also include alarms without site_id
  const alarmsWithoutSiteId = alarms.filter(a => !a.site_id);
  
  return [...uniqueAlarms, ...alarmsWithoutSiteId];
}

export const useAlarmStore = create<AlarmState>((set, get) => {
  let pendingRequest: Promise<void> | null = null;
  
  return {
    alarms: [],
    selectedAlarm: null,
    stats: null,
    filters: {},
    pagination: {
      limit: 20,
      offset: 0,
      total: 0,
    },
    loading: false,
    error: null,

    fetchAlarms: async (filters, limit, offset, aggregateBySite) => {
      // Cancel previous request if still pending
      if (pendingRequest) {
        try {
          await pendingRequest;
        } catch (e) {
          // Ignore errors from previous request
        }
      }
      
      // Clear cache for site summary to ensure fresh data
      if (aggregateBySite) {
        dataService.invalidateCache('/api/v1/alarms');
      }
      
      // Create new request
      pendingRequest = (async () => {
        set({ loading: true, error: null });
        
        try {
          const response = await getAlarms(filters, limit, offset, aggregateBySite);
          
          if (response.status === 'success' && response.data) {
            let alarms = response.data.alarms || [];
            
            // CRITICAL: Deduplicate by site_id if aggregateBySite is true
            if (aggregateBySite && alarms.length > 0) {
              alarms = deduplicateSiteAlarms(alarms);
            }
            
            // Ensure total is correct
            const total = typeof response.data.total === 'number' 
              ? response.data.total 
              : alarms.length;
            
            // Set data atomically
            set({
              alarms: alarms,
              pagination: {
                limit: response.data.limit || limit || 20,
                offset: response.data.offset || offset || 0,
                total: total,
              },
              loading: false,
            });
          } else {
            set({ 
              alarms: [],
              error: response.message || 'Failed to fetch alarms', 
              loading: false 
            });
          }
        } catch (error: any) {
          console.error('Error fetching alarms:', error);
          const isRateLimit = error?.message?.toLowerCase().includes('rate limit') || 
                             error?.response?.status === 429;
          set({ 
            alarms: isRateLimit ? get().alarms : [],
            error: isRateLimit ? null : (error?.message || 'An error occurred while fetching alarms'), 
            loading: false 
          });
        } finally {
          pendingRequest = null;
        }
      })();
      
      await pendingRequest;
    },

    fetchAlarm: async (alarmId) => {
      set({ loading: true, error: null });
      try {
        const response = await getAlarm(alarmId);
        if (response.status === 'success' && response.data) {
          set({ selectedAlarm: response.data, loading: false });
        } else {
          set({ error: response.message || 'Failed to fetch alarm', loading: false });
        }
      } catch (error) {
        set({ error: 'An error occurred while fetching alarm', loading: false });
      }
    },

    fetchStats: async (startTime, endTime) => {
      try {
        const response = await getAlarmStats(startTime, endTime);
        if (response.status === 'success' && response.data) {
          set({ stats: response.data });
        }
      } catch (error) {
        console.error('Failed to fetch alarm stats:', error);
      }
    },

    setFilters: (filters) => {
      set({ filters });
    },

    setPagination: (limit, offset) => {
      set((state) => ({
        pagination: {
          ...state.pagination,
          limit,
          offset,
        },
      }));
    },

    setSelectedAlarm: (alarm) => {
      set({ selectedAlarm: alarm });
    },

    clearError: () => {
      set({ error: null });
    },
  };
});
