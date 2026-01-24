/**
 * Site Diagnostic Store
 * Manages diagnostic generation state for sites
 * Persists state across page navigation
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SiteDiagnosticState {
  siteId: string;
  isGenerating: boolean;
  startTime: number | null;
  diagnosticId: string | null;
  // Maximum duration for diagnostic (30 minutes)
  maxDuration: number; // milliseconds
}

interface SiteDiagnosticStore {
  // Map of siteId -> diagnostic state
  diagnostics: Record<string, SiteDiagnosticState>;
  
  // Actions
  startDiagnostic: (siteId: string, diagnosticId?: string) => void;
  completeDiagnostic: (siteId: string) => void;
  getDiagnosticState: (siteId: string) => SiteDiagnosticState | null;
  isGeneratingForSite: (siteId: string) => boolean;
  clearDiagnostic: (siteId: string) => void;
}

export const useSiteDiagnosticStore = create<SiteDiagnosticStore>()(
  persist(
    (set, get) => ({
      diagnostics: {},

      startDiagnostic: (siteId: string, diagnosticId?: string) => {
        set((state) => ({
          diagnostics: {
            ...state.diagnostics,
            [siteId]: {
              siteId,
              isGenerating: true,
              startTime: Date.now(),
              diagnosticId: diagnosticId || null,
              maxDuration: 30 * 60 * 1000, // 30 minutes
            },
          },
        }));
      },

      completeDiagnostic: (siteId: string) => {
        set((state) => {
          const newDiagnostics = { ...state.diagnostics };
          if (newDiagnostics[siteId]) {
            newDiagnostics[siteId] = {
              ...newDiagnostics[siteId],
              isGenerating: false,
            };
          }
          return { diagnostics: newDiagnostics };
        });
      },

      getDiagnosticState: (siteId: string) => {
        return get().diagnostics[siteId] || null;
      },

      isGeneratingForSite: (siteId: string) => {
        const state = get().diagnostics[siteId];
        if (!state?.isGenerating) {
          return false;
        }
        
        // Check if diagnostic has exceeded max duration
        // Only check timeout, don't auto-complete here (let the polling mechanism handle it)
        if (state.startTime) {
          const elapsed = Date.now() - state.startTime;
          const maxDuration = state.maxDuration || 30 * 60 * 1000; // Default 30 minutes
          if (elapsed > maxDuration) {
            // Exceeded max duration, but don't auto-complete here
            // The polling mechanism will check and complete if diagnostic is done
            // Return false to indicate it's no longer generating (timeout)
            console.log(`[SiteDiagnosticStore] Diagnostic for site ${siteId} exceeded max duration (${elapsed}ms > ${maxDuration}ms)`);
            return false;
          }
        }
        
        return true;
      },

      clearDiagnostic: (siteId: string) => {
        set((state) => {
          const newDiagnostics = { ...state.diagnostics };
          delete newDiagnostics[siteId];
          return { diagnostics: newDiagnostics };
        });
      },
    }),
    {
      name: 'site-diagnostic-storage',
      // Only persist isGenerating and startTime, not diagnosticId (it's temporary)
      partialize: (state) => ({
        diagnostics: Object.fromEntries(
          Object.entries(state.diagnostics).map(([siteId, diagnostic]) => [
            siteId,
            {
              siteId,
              isGenerating: diagnostic.isGenerating,
              startTime: diagnostic.startTime,
              diagnosticId: null, // Don't persist diagnosticId
              maxDuration: diagnostic.maxDuration || 30 * 60 * 1000, // Persist maxDuration
            },
          ])
        ),
      }),
    }
  )
);

