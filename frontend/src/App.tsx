/**
 * Main Application Component
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ToastContainer } from './components/ui/Toast';
import { useToastStore } from './store/useToastStore';
import { useSiteStore } from './store/useSiteStore';
import { useSiteDiagnosticStore } from './store/useSiteDiagnosticStore';
import { websocketEventManager } from './services/websocketEventManager';
import { Dashboard } from './pages/Dashboard';
import { DeviceManagement } from './pages/DeviceManagement';
import { AlarmManagement } from './pages/AlarmManagement';
import { DiagnosticReports } from './pages/DiagnosticReports';
import { DiagnosticPage } from './pages/DiagnosticPage';
import { DataFlowVisualization } from './pages/DataFlowVisualization';
import { DataCenterMapPage } from './pages/DataCenterMap';
import { SiteDetails } from './pages/SiteDetails';

function App() {
  const { toasts, removeToast } = useToastStore();
  const { sites, fetchSites, loading: sitesLoading } = useSiteStore();
  
  // Preload global shared data on app mount
  // This ensures sites data is available to all pages without duplicate fetches
  useEffect(() => {
    // Only fetch if sites list is empty and not currently loading
    if (sites.length === 0 && !sitesLoading) {
      console.log('[App] Preloading sites data...');
      fetchSites();
    }
  }, [sites.length, sitesLoading, fetchSites]);
  
  // Global listener for diagnostic_created events - shows toast on any page
  useEffect(() => {
    const unsubscribeDiagnosticCreated = websocketEventManager.subscribe('diagnostic_created', (data: any) => {
      console.log('[App] Received diagnostic_created event:', data);
      const diagnosticId = data?.alarm_id || data?.id;
      const siteId = data?.site_id;
      
      if (!diagnosticId) {
        console.warn('[App] diagnostic_created event missing diagnostic ID');
        return;
      }
      
      // Get current state from store (not from closure)
      const { hasShownToast, markToastShown, getDiagnosticState, completeDiagnostic } = useSiteDiagnosticStore.getState();
      const { sites } = useSiteStore.getState();
      
      // Only show toast if we haven't shown it for this diagnostic yet
      if (!hasShownToast(diagnosticId)) {
        markToastShown(diagnosticId);
        
        // Get site name from store
        const site = sites.find(s => s.site_id === siteId);
        const siteName = site?.site_name || siteId || 'Unknown site';
        
        // Complete diagnostic state if it was generating
        if (siteId) {
          const diagnosticState = getDiagnosticState(siteId);
          if (diagnosticState?.isGenerating) {
            completeDiagnostic(siteId);
          }
        }
        
        // Show global toast notification
        const { addToast } = useToastStore.getState();
        addToast(`AI diagnostic analysis completed for site: ${siteName}`, 'success');
        console.log('[App] Displayed global toast for diagnostic:', diagnosticId);
      } else {
        console.log('[App] Toast already shown for diagnostic:', diagnosticId);
      }
    });
    
    return () => {
      unsubscribeDiagnosticCreated();
    };
  }, []); // Empty dependency array - use getState() to access current state

  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/datacenter" element={<DataCenterMapPage />} />
          <Route path="/datacenter/sites/:siteId" element={<SiteDetails />} />
          <Route path="/devices" element={<DeviceManagement />} />
          <Route path="/alarms" element={<AlarmManagement />} />
          <Route path="/alarms/:alarmId" element={<AlarmManagement />} />
          <Route path="/diagnostics" element={<DiagnosticReports />} />
          <Route path="/diagnostics/:siteId" element={<DiagnosticPage />} />
          <Route path="/flow" element={<DataFlowVisualization />} />
        </Routes>
        <ToastContainer toasts={toasts} onClose={removeToast} />
      </Layout>
    </BrowserRouter>
  );
}

export default App;

