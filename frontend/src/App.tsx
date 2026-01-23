/**
 * Main Application Component
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ToastContainer } from './components/ui/Toast';
import { useToastStore } from './store/useToastStore';
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

  return (
    <BrowserRouter>
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

