/**
 * Site Store
 * Zustand store for site state management
 */

import { create } from 'zustand';
import { Site, SiteStats, SiteRules, getSites, getSite, getSiteStats, getSiteRules, getSiteDevices, deleteSite, updateSite } from '@/api/sites';

interface SiteState {
  sites: Site[];
  selectedSite: Site | null;
  siteStats: Record<string, SiteStats>;
  siteRules: Record<string, SiteRules>;
  siteDevices: Record<string, any[]>;
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchSites: () => Promise<void>;
  fetchSite: (siteId: string) => Promise<void>;
  fetchSiteStats: (siteId: string) => Promise<void>;
  fetchSiteRules: (siteId: string) => Promise<void>;
  fetchSiteDevices: (siteId: string) => Promise<void>;
  deleteSite: (siteId: string, deleteData?: boolean) => Promise<void>;
  updateSite: (siteId: string, siteData: Partial<Site>) => Promise<void>;
  setSelectedSite: (site: Site | null) => void;
  clearError: () => void;
}

export const useSiteStore = create<SiteState>((set, get) => ({
  sites: [],
  selectedSite: null,
  siteStats: {},
  siteRules: {},
  siteDevices: {},
  loading: false,
  error: null,

  fetchSites: async () => {
    set({ loading: true, error: null });
    try {
      console.log('[SiteStore] Fetching sites...');
      const response = await getSites();
      console.log('[SiteStore] Sites response:', JSON.stringify(response, null, 2));
      
      // Handle different response formats
      if (response.status === 'success') {
        // Check if data is nested or direct
        const sitesList = response.data?.sites || response.data || [];
        console.log('[SiteStore] Parsed sites list:', sitesList.length, 'sites');
        console.log('[SiteStore] Sites data:', sitesList);
        
        if (Array.isArray(sitesList) && sitesList.length > 0) {
          console.log('[SiteStore] ✅ Setting sites:', sitesList.length, 'sites');
          sitesList.forEach((s, i) => {
            console.log(`[SiteStore] Site ${i}:`, {
              id: s.site_id,
              name: s.site_name,
              lat: s.latitude,
              lng: s.longitude,
              hasCoords: !!(s.latitude && s.longitude)
            });
          });
          set({ sites: sitesList, loading: false, error: null });
        } else {
          console.warn('[SiteStore] ⚠️ No sites in response or empty array');
          set({ sites: [], loading: false, error: null });
        }
      } else {
        console.warn('[SiteStore] ❌ Failed to fetch sites:', response);
        const errorMsg = response.message || response.data?.message || 'Failed to fetch sites';
        set({ error: errorMsg, loading: false, sites: [] });
      }
    } catch (error: any) {
      console.error('[SiteStore] ❌ Error fetching sites:', error);
      console.error('[SiteStore] Error details:', error?.response?.data || error?.message);
      set({ error: error?.message || 'An error occurred while fetching sites', loading: false, sites: [] });
    }
  },

  fetchSite: async (siteId: string) => {
    set({ loading: true, error: null });
    try {
      console.log('[SiteStore] Fetching site:', siteId);
      const response = await getSite(siteId);
      console.log('[SiteStore] Site response:', JSON.stringify(response, null, 2));
      if (response.status === 'success' && response.data) {
        const site = response.data;
        console.log('[SiteStore] ✅ Site fetched successfully:', site.site_id, site.site_name);
        set({ selectedSite: site, loading: false, error: null });
        
        // Update sites list if site exists
        const sites = get().sites;
        const siteIndex = sites.findIndex(s => s.site_id === siteId);
        if (siteIndex >= 0) {
          sites[siteIndex] = site;
          set({ sites });
        } else {
          set({ sites: [...sites, site] });
        }
      } else {
        console.warn('[SiteStore] ❌ Failed to fetch site:', response);
        const errorMsg = response.message || 'Failed to fetch site';
        set({ error: errorMsg, loading: false, selectedSite: null });
      }
    } catch (error: any) {
      console.error('[SiteStore] ❌ Error fetching site:', error);
      console.error('[SiteStore] Error details:', error?.response?.data || error?.message);
      set({ error: error?.message || 'An error occurred while fetching site', loading: false, selectedSite: null });
    }
  },

  fetchSiteStats: async (siteId: string) => {
    try {
      const response = await getSiteStats(siteId);
      if (response.status === 'success' && response.data) {
        const stats = get().siteStats;
        set({ siteStats: { ...stats, [siteId]: response.data } });
      }
    } catch (error) {
      console.error(`[SiteStore] Error fetching site stats for ${siteId}:`, error);
    }
  },

  fetchSiteRules: async (siteId: string) => {
    try {
      const response = await getSiteRules(siteId);
      if (response.status === 'success' && response.data) {
        const rules = get().siteRules;
        set({ siteRules: { ...rules, [siteId]: response.data } });
      }
    } catch (error) {
      console.error(`[SiteStore] Error fetching site rules for ${siteId}:`, error);
    }
  },

  fetchSiteDevices: async (siteId: string) => {
    try {
      console.log(`[SiteStore] Fetching devices for site ${siteId}`);
      const response = await getSiteDevices(siteId);
      console.log(`[SiteStore] Site devices response for ${siteId}:`, response);
      console.log(`[SiteStore] Response type:`, typeof response);
      console.log(`[SiteStore] Response status:`, response?.status);
      console.log(`[SiteStore] Response data:`, response?.data);
      
      if (response && response.status === 'success' && response.data) {
        const devices = response.data.devices || [];
        console.log(`[SiteStore] ✅ Received ${devices.length} devices for site ${siteId}:`, devices.map(d => ({ 
          id: d.device_id, 
          status: d.status, 
          last_seen: d.last_seen,
          site_id: d.metadata?.site_id 
        })));
        const currentDevices = get().siteDevices;
        set({ siteDevices: { ...currentDevices, [siteId]: devices } });
        console.log(`[SiteStore] ✅ Updated siteDevices state for ${siteId}, total devices:`, devices.length);
        console.log(`[SiteStore] Current siteDevices state:`, get().siteDevices);
      } else {
        console.warn(`[SiteStore] ❌ Failed to fetch devices for site ${siteId}:`, response);
        console.warn(`[SiteStore] Response structure:`, {
          hasResponse: !!response,
          hasStatus: !!response?.status,
          hasData: !!response?.data,
          statusValue: response?.status,
          dataValue: response?.data
        });
      }
    } catch (error: any) {
      console.error(`[SiteStore] ❌ Error fetching site devices for ${siteId}:`, error);
      console.error(`[SiteStore] Error details:`, error?.response?.data || error?.message);
      console.error(`[SiteStore] Error stack:`, error?.stack);
    }
  },

  deleteSite: async (siteId: string, deleteData: boolean = false) => {
    try {
      console.log(`[SiteStore] Deleting site: ${siteId}, deleteData: ${deleteData}`);
      const response = await deleteSite(siteId, deleteData);
      if (response.status === 'success') {
        // Remove from sites list
        const sites = get().sites.filter(s => s.site_id !== siteId);
        set({ sites });
        
        // Clear selected site if it's the deleted one
        const selectedSite = get().selectedSite;
        if (selectedSite && selectedSite.site_id === siteId) {
          set({ selectedSite: null });
        }
        
        // Clear cached data
        const siteStats = get().siteStats;
        delete siteStats[siteId];
        const siteRules = get().siteRules;
        delete siteRules[siteId];
        const siteDevices = get().siteDevices;
        delete siteDevices[siteId];
        
        set({ siteStats, siteRules, siteDevices });
        
        console.log(`[SiteStore] ✅ Site ${siteId} deleted successfully`);
      } else {
        const errorMsg = response.message || 'Failed to delete site';
        set({ error: errorMsg });
        throw new Error(errorMsg);
      }
    } catch (error: any) {
      console.error(`[SiteStore] ❌ Error deleting site ${siteId}:`, error);
      const errorMsg = error?.message || 'An error occurred while deleting site';
      set({ error: errorMsg });
      throw error;
    }
  },

  updateSite: async (siteId: string, siteData: Partial<Site>) => {
    set({ loading: true, error: null });
    try {
      console.log(`[SiteStore] Updating site: ${siteId}`, siteData);
      const response = await updateSite(siteId, siteData);
      if (response.status === 'success' && response.data) {
        const updatedSite = response.data;
        console.log(`[SiteStore] ✅ Site updated successfully:`, updatedSite.site_id);
        
        // Update selected site if it's the updated one
        const selectedSite = get().selectedSite;
        if (selectedSite && selectedSite.site_id === siteId) {
          set({ selectedSite: updatedSite });
        }
        
        // Update sites list
        const sites = get().sites;
        const siteIndex = sites.findIndex(s => s.site_id === siteId);
        if (siteIndex >= 0) {
          sites[siteIndex] = updatedSite;
          set({ sites });
        } else {
          set({ sites: [...sites, updatedSite] });
        }
        
        set({ loading: false, error: null });
      } else {
        const errorMsg = response.message || 'Failed to update site';
        set({ error: errorMsg, loading: false });
        throw new Error(errorMsg);
      }
    } catch (error: any) {
      console.error(`[SiteStore] ❌ Error updating site ${siteId}:`, error);
      const errorMsg = error?.message || 'An error occurred while updating site';
      set({ error: errorMsg, loading: false });
      throw error;
    }
  },

  setSelectedSite: (site: Site | null) => {
    set({ selectedSite: site });
  },

  clearError: () => {
    set({ error: null });
  },
}));

