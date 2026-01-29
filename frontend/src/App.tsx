/**
 * Main Application Component
 */

import { useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ToastContainer } from './components/ui/Toast';
import { useToastStore } from './store/useToastStore';
import { useSiteStore } from './store/useSiteStore';
import { useSiteDiagnosticStore } from './store/useSiteDiagnosticStore';
import { useAuthStore } from './store/useAuthStore';
import { websocketEventManager } from './services/websocketEventManager';
import { Dashboard } from './pages/Dashboard';
import { DeviceManagement } from './pages/DeviceManagement';
import { AlarmManagement } from './pages/AlarmManagement';
import { DiagnosticReports } from './pages/DiagnosticReports';
import { DiagnosticPage } from './pages/DiagnosticPage';
import { DataFlowVisualization } from './pages/DataFlowVisualization';
import { DataCenterMapPage } from './pages/DataCenterMap';
import { SiteDetails } from './pages/SiteDetails';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

function App() {
  const { toasts, removeToast } = useToastStore();
  const { sites, fetchSites, loading: sitesLoading } = useSiteStore();
  const { isAuthenticated } = useAuthStore();
  const loginTimeRef = useRef<number | null>(null);
  
  // Track login time to filter historical events
  useEffect(() => {
    if (isAuthenticated && !loginTimeRef.current) {
      loginTimeRef.current = Date.now();
      console.log('[App] User logged in, setting login time for event filtering');
    } else if (!isAuthenticated) {
      loginTimeRef.current = null;
    }
  }, [isAuthenticated]);
  
  // Preload global shared data on app mount
  // This ensures sites data is available to all pages without duplicate fetches
  useEffect(() => {
    // Only fetch once on mount if sites list is empty
    if (sites.length === 0 && !sitesLoading) {
      console.log('[App] Preloading sites data...');
      fetchSites();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount
  
  // Global listener for diagnostic_created events - shows toast on any page
  // Only show toast for NEW diagnostics created AFTER login (not historical ones)
  useEffect(() => {
    const unsubscribeDiagnosticCreated = websocketEventManager.subscribe('diagnostic_created', (data: any) => {
      console.log('[App] Received diagnostic_created event:', data);
      const diagnosticId = data?.alarm_id || data?.id;
      const siteId = data?.site_id;
      const eventTimestamp = data?.timestamp ? new Date(data.timestamp).getTime() : Date.now();
      
      if (!diagnosticId) {
        console.warn('[App] diagnostic_created event missing diagnostic ID');
        return;
      }
      
      // Get current login time (reset when user logs in)
      const currentLoginTime = loginTimeRef.current;
      if (!currentLoginTime) {
        // User not logged in yet, ignore event
        console.log('[App] User not logged in, ignoring diagnostic event:', diagnosticId);
        return;
      }
      
      // Ignore events that happened before login (historical events)
      // Allow 5 second buffer for clock differences
      if (eventTimestamp < currentLoginTime - 5000) {
        console.log('[App] Ignoring historical diagnostic event (before login):', diagnosticId);
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
  }, []); // Empty dependency array - use refs and getState() to access current state

  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        {/* Protected routes */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
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
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

