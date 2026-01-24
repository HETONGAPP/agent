/**
 * Site Details Page
 * Shows detailed information about a specific site
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, MapPin, Clock, Settings, RefreshCw, Edit, Trash2, Brain } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Modal } from '@/components/ui/Modal';
import { AddDeviceForm } from '@/components/sites/AddDeviceForm';
import { EditDeviceForm } from '@/components/devices/EditDeviceForm';
import { AddRuleForm } from '@/components/sites/AddRuleForm';
import { EditSiteForm } from '@/components/sites/EditSiteForm';
import { SiteOverviewTab } from '@/components/sites/SiteOverviewTab';
import { SiteDevicesTab } from '@/components/sites/SiteDevicesTab';
import { SiteRulesTab } from '@/components/sites/SiteRulesTab';
import { SiteSettingsTab } from '@/components/sites/SiteSettingsTab';
import { SiteAlarmsTab } from '@/components/sites/SiteAlarmsTab';
import { SiteDeleteModal } from '@/components/sites/SiteDeleteModal';
import { SiteRemoveDeviceModal } from '@/components/sites/SiteRemoveDeviceModal';
import { useSiteDetails } from '@/hooks/useSiteDetails';
import { useToastStore } from '@/store/useToastStore';
import { useSiteDiagnosticStore } from '@/store/useSiteDiagnosticStore';
import { updateSiteRule, generateSiteDiagnostic, getSiteDiagnostics } from '@/api/sites';
import { Device, Diagnostic } from '@/types';
import { DiagnosticOutput } from '@/components/diagnostics/DiagnosticOutput';

export const SiteDetails = () => {
  const { siteId } = useParams<{ siteId: string }>();
  const navigate = useNavigate();
  const { addToast } = useToastStore();
  
  // Use global diagnostic store for persistent state
  const {
    isGeneratingForSite,
    startDiagnostic,
    completeDiagnostic,
    getDiagnosticState,
  } = useSiteDiagnosticStore();

  const {
    // Site data
    selectedSite,
    stats,
    devices,
    siteRules,
    loading,
    error,
    
    // UI state
    activeTab,
    setActiveTab,
    showAddDeviceModal,
    setShowAddDeviceModal,
    showAddRuleModal,
    setShowAddRuleModal,
    showEditRuleModal,
    setShowEditRuleModal,
    editingRule,
    setEditingRule,
    showEditSiteModal,
    setShowEditSiteModal,
    showDeleteModal,
    setShowDeleteModal,
    isDeleting,
    setIsDeleting,
    showRemoveDeviceModal,
    setShowRemoveDeviceModal,
    deviceToRemove,
    setDeviceToRemove,
    isRemovingDevice,
    setIsRemovingDevice,
    
    // Time series data
    deviceTimeSeries,
    loadingTimeSeries,
    selectedDevices,
    setSelectedDevices,
    selectedMetric,
    setSelectedMetric,
    timeRange,
    setTimeRange,
    interval,
    setInterval,
    availableMetrics,
    
    // WebSocket
    isSiteAlive,
    
    // Actions
    fetchSite,
    fetchSiteStats,
    fetchSiteDevices,
    fetchSiteRules,
    deleteSite,
    removeDevice,
    updateSiteInStore,
  } = useSiteDetails({ siteId });

  // Local state for device editing
  const [showEditDeviceModal, setShowEditDeviceModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);

  // Diagnostic state - use global store for persistent state
  // Check if generating, but also verify it hasn't timed out
  const isGeneratingDiagnostic = siteId ? isGeneratingForSite(siteId) : false;
  const [diagnosticResult, setDiagnosticResult] = useState<Diagnostic | null>(null);
  const [showDiagnosticModal, setShowDiagnosticModal] = useState(false);
  const [diagnosticTimeRange] = useState<string>('-24h'); // Time range for diagnostic (currently fixed to -24h)
  
  // Use ref to track component mount status
  const isMountedRef = useRef(true);
  
  useEffect(() => {
    // Set mounted flag on mount
    isMountedRef.current = true;
    
    return () => {
      // Set unmounted flag on unmount
      isMountedRef.current = false;
    };
  }, []);
  
  // Check for persisted diagnostic state on mount and validate if diagnostic actually completed
  useEffect(() => {
    if (!siteId) {
      return;
    }
    
    // Get current diagnostic state
    const currentState = getDiagnosticState(siteId);
    if (!currentState || !currentState.isGenerating || !currentState.startTime) {
      // No active diagnostic, nothing to check
      return;
    }
    
    const checkDiagnosticStatus = async () => {
      // Re-get state in case it changed
      const state = getDiagnosticState(siteId);
      if (!state || !state.isGenerating || !state.startTime) {
        console.log('[SiteDetails] Diagnostic state no longer active, stopping check');
        return;
      }
      
      const startTime = state.startTime; // Use state.startTime, not diagnosticState
      const startTimeISO = new Date(startTime).toISOString();
      console.log(`[SiteDetails] Checking diagnostic status. Start time: ${startTimeISO} (${startTime})`);
      
      try {
        // Check if there's a new diagnostic record created after the start time
        // Query diagnostics from start time to now
        const response = await getSiteDiagnostics(siteId, {
          start_time: startTimeISO,
          limit: 10, // Check last 10 diagnostics
        });
        
        console.log('[SiteDetails] Diagnostic query response:', response);
        
        if (response.status === 'success' && response.data) {
          const diagnostics = Array.isArray(response.data) ? response.data : response.data.diagnostics || [];
          console.log(`[SiteDetails] Found ${diagnostics.length} diagnostic records`);
          
          // Check if any diagnostic was created after our start time
          // We need to be more strict: diagnostic must be created AFTER start time (not before)
          const hasNewDiagnostic = diagnostics.some((diag: any) => {
            // Try multiple possible timestamp fields
            const diagTime = diag.generated_at || diag.timestamp || diag._time;
            if (!diagTime) {
              console.log('[SiteDetails] Diagnostic record missing timestamp:', diag);
              return false;
            }
            
            // Parse timestamp (could be ISO string or timestamp)
            let diagTimestamp: number;
            try {
              if (typeof diagTime === 'string') {
                diagTimestamp = new Date(diagTime).getTime();
                // Handle invalid date
                if (isNaN(diagTimestamp)) {
                  console.log('[SiteDetails] Invalid date string:', diagTime);
                  return false;
                }
              } else if (typeof diagTime === 'number') {
                diagTimestamp = diagTime;
              } else {
                console.log('[SiteDetails] Unknown timestamp format:', diagTime, typeof diagTime);
                return false;
              }
              
              // Check if diagnostic was created after start time
              // Use a small buffer (2 seconds) to account for processing time
              const timeDiff = diagTimestamp - startTime;
              const isNew = timeDiff >= -2000; // Allow 2 second buffer
              
              if (isNew) {
                console.log(`[SiteDetails] ✓ Found new diagnostic: ${diag.alarm_id || 'unknown'}`);
                console.log(`  - Diagnostic time: ${new Date(diagTimestamp).toISOString()} (${diagTimestamp})`);
                console.log(`  - Start time: ${startTimeISO} (${startTime})`);
                console.log(`  - Time difference: ${timeDiff}ms`);
              } else {
                console.log(`[SiteDetails] ✗ Diagnostic too old: ${diag.alarm_id || 'unknown'}, diff: ${timeDiff}ms`);
              }
              
              return isNew;
            } catch (parseError) {
              console.error('[SiteDetails] Error parsing timestamp:', diagTime, parseError);
              return false;
            }
          });
          
          if (hasNewDiagnostic) {
            // Diagnostic has completed, update state
            console.log('[SiteDetails] Found new diagnostic record, completing state');
            completeDiagnostic(siteId);
          } else {
            console.log('[SiteDetails] No new diagnostic found yet, continuing to wait');
          }
        } else {
          console.log('[SiteDetails] Diagnostic query failed or no data:', response);
        }
      } catch (error) {
        console.error('[SiteDetails] Error checking diagnostic status:', error);
        // Don't fail silently - if check fails, we'll rely on timeout
      }
    };
    
    // Check immediately on mount
    checkDiagnosticStatus();
    
    // Also set up periodic check every 5 seconds while generating (more frequent for better UX)
    const intervalId = window.setInterval(() => {
      // Re-check if still generating (state might have changed)
      const currentState = getDiagnosticState(siteId);
      if (!siteId || !currentState || !currentState.isGenerating || !isGeneratingForSite(siteId)) {
        console.log('[SiteDetails] Diagnostic no longer generating, stopping polling');
        window.clearInterval(intervalId);
        return;
      }
      
      // Call async function without awaiting (fire and forget)
      checkDiagnosticStatus().catch((err) => {
        console.error('[SiteDetails] Error in periodic diagnostic check:', err);
      });
    }, 5000); // Check every 5 seconds for faster detection
    
    return () => {
      window.clearInterval(intervalId);
    };
  }, [siteId, getDiagnosticState, completeDiagnostic, isGeneratingForSite]);
  
  // Cleanup: Ensure state is reset if component unmounts and diagnostic completes
  useEffect(() => {
    return () => {
      // Don't reset on unmount - we want to preserve state for when user returns
      // The timeout check in the store will handle stale states
    };
  }, []);

  // Check if we should show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
        <p className="ml-4 text-gray-400">Loading site details...</p>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400 mb-4">{error}</p>
        <p className="text-gray-400 mb-4 text-sm">Site ID: {siteId}</p>
        <Button variant="secondary" onClick={() => navigate('/datacenter')}>
          <ArrowLeft size={16} className="mr-2" />
          Back to Map
        </Button>
      </div>
    );
  }

  // Show not found state
  if (!selectedSite) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400 mb-4">Site not found</p>
        <p className="text-gray-400 mb-4 text-sm">Site ID: {siteId}</p>
        <Button variant="secondary" onClick={() => navigate('/datacenter')}>
          <ArrowLeft size={16} className="mr-2" />
          Back to Map
        </Button>
      </div>
    );
  }

  // Handlers
  const handleDeleteSite = async (deleteData: boolean) => {
    if (!siteId || !selectedSite) return;
    
    setIsDeleting(true);
    try {
      await deleteSite(siteId, deleteData);
      addToast(
        `Site ${selectedSite.site_name} deleted successfully` + 
        (deleteData ? ' (all data deleted)' : ' (data preserved)'),
        'success'
      );
      navigate('/datacenter');
    } catch (error: any) {
      addToast(error?.message || 'Failed to delete site', 'error');
    } finally {
      setIsDeleting(false);
      setShowDeleteModal(false);
    }
  };

  const handleRemoveDevice = async (deleteData: boolean) => {
    if (!deviceToRemove || !siteId) return;
    
    setIsRemovingDevice(true);
    try {
      await removeDevice(deviceToRemove.device_id, deleteData);
      fetchSiteDevices(siteId);
      fetchSiteStats(siteId);
      addToast(
        `Device ${deviceToRemove.device_id} removed successfully` + 
        (deleteData ? ' (data deleted)' : ' (data preserved)'),
        'success'
      );
      setShowRemoveDeviceModal(false);
      setDeviceToRemove(null);
    } catch (error: any) {
      addToast(error?.message || 'Failed to remove device', 'error');
    } finally {
      setIsRemovingDevice(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
        <button
          onClick={() => navigate('/datacenter')}
          className="hover:text-white transition-colors duration-200 flex items-center gap-1.5 group"
        >
          <span>Data Center</span>
          <span className="text-gray-600">/</span>
        </button>
        <span className="text-white font-medium">{selectedSite.site_name}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-gray-700/50">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/datacenter')}
            className="p-2 rounded-lg hover:bg-gray-800/50 transition-all duration-200 group -ml-2"
            aria-label="Back to Data Center"
          >
            <ArrowLeft size={20} className="text-gray-400 group-hover:text-white group-hover:-translate-x-1 transition-all duration-200" />
          </button>
          <div>
            <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">{selectedSite.site_name}</h1>
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-gray-400 text-sm font-mono bg-gray-800/50 px-2.5 py-1 rounded-md border border-gray-700/50 flex-shrink-0">
                ID: {selectedSite.site_id}
              </span>
              {isSiteAlive && (
                <span className="flex items-center gap-2 text-sm text-green-400 bg-green-500/10 px-2.5 py-1 rounded-md border border-green-500/20 flex-shrink-0">
                  <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse shadow-lg shadow-green-400/50 flex-shrink-0"></span>
                  <span>Live</span>
                </span>
              )}
              {!isSiteAlive && (
                <span className="flex items-center gap-2 text-sm text-gray-400 bg-gray-800/50 px-2.5 py-1 rounded-md border border-gray-700/50 flex-shrink-0">
                  <span className="h-2 w-2 rounded-full bg-gray-500 flex-shrink-0"></span>
                  <span>No Active Devices</span>
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Diagnostic Progress Indicator */}
          {isGeneratingDiagnostic && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-lg">
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-purple-300">Analyzing...</span>
            </div>
          )}
          
          <Button
            variant="primary"
            size="sm"
            onClick={async () => {
              if (!siteId) return;
              
              // Start diagnostic state with current timestamp
              const diagnosticStartTime = Date.now();
              startDiagnostic(siteId);
              
              console.log(`[SiteDetails] Starting diagnostic for site ${siteId} at ${new Date(diagnosticStartTime).toISOString()}`);
              
              try {
                const response = await generateSiteDiagnostic(siteId, diagnosticTimeRange);
                
                console.log(`[SiteDetails] Diagnostic API call completed for site ${siteId}`);
                
                // Check if component is still mounted before updating UI state
                if (!isMountedRef.current) {
                  // Component unmounted during API call
                  // Don't complete state here - let the polling mechanism detect completion
                  console.log('[SiteDetails] Component unmounted, state will be checked by polling');
                  return;
                }
                
                // Verify the diagnostic was actually created by checking the response
                if (response.status === 'success' && response.data) {
                  // Diagnostic completed successfully
                  console.log('[SiteDetails] Diagnostic completed successfully, updating state');
                  completeDiagnostic(siteId);
                  
                  setDiagnosticResult(response.data);
                  setShowDiagnosticModal(true);
                  addToast('AI diagnostic analysis completed', 'success');
                } else {
                  // Diagnostic failed
                  console.log('[SiteDetails] Diagnostic failed:', response.message);
                  completeDiagnostic(siteId);
                  addToast(response.message || 'Failed to generate diagnostic', 'error');
                }
              } catch (error: any) {
                console.error('[SiteDetails] Error generating diagnostic:', error);
                
                // Only complete state if component is still mounted
                // If unmounted, let polling mechanism handle it
                if (isMountedRef.current && siteId) {
                  completeDiagnostic(siteId);
                  addToast(error?.message || 'Failed to generate diagnostic', 'error');
                } else {
                  console.log('[SiteDetails] Component unmounted during error, state will be checked by polling');
                }
              }
            }}
            disabled={isGeneratingDiagnostic || !siteId}
            className="group hover:bg-purple-600/90 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-200"
          >
            {isGeneratingDiagnostic ? (
              <>
                <LoadingSpinner size="sm" className="mr-2" />
                Analyzing...
              </>
            ) : (
              <>
                <Brain size={16} className="mr-2 group-hover:scale-110 transition-transform" />
                Start AI Diagnostic Analysis
              </>
            )}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowEditSiteModal(true)}
            className="group hover:bg-blue-600/20 hover:border-blue-500/50 transition-all duration-200"
          >
            <Edit size={16} className="mr-2" />
            Edit Site
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              if (siteId) {
                fetchSite(siteId);
                fetchSiteStats(siteId);
                fetchSiteDevices(siteId);
              }
            }}
            className="group hover:bg-blue-600/20 hover:border-blue-500/50 transition-all duration-200"
          >
            <RefreshCw size={16} className="mr-2 group-hover:rotate-180 transition-transform duration-500" />
            Refresh
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setShowDeleteModal(true)}
            className="group hover:bg-red-600/90 hover:shadow-lg hover:shadow-red-500/20 transition-all duration-200"
          >
            <Trash2 size={16} className="mr-2 group-hover:scale-110 transition-transform" />
            Delete Site
          </Button>
        </div>
      </div>

      {/* Site Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {selectedSite.location && (
          <div className="card flex items-center gap-4 p-5 border border-gray-700/50 hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/10 transition-all duration-300 group">
            <div className="p-3 bg-blue-500/10 rounded-xl group-hover:bg-blue-500/20 transition-colors border border-blue-500/20">
              <MapPin className="text-blue-400 group-hover:text-blue-300 transition-colors" size={24} />
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Location</div>
              <div className="text-white font-semibold text-lg">{selectedSite.location || 'Not specified'}</div>
            </div>
          </div>
        )}
        {selectedSite.timezone && (
          <div className="card flex items-center gap-4 p-5 border border-gray-700/50 hover:border-green-500/50 hover:shadow-lg hover:shadow-green-500/10 transition-all duration-300 group">
            <div className="p-3 bg-green-500/10 rounded-xl group-hover:bg-green-500/20 transition-colors border border-green-500/20">
              <Clock className="text-green-400 group-hover:text-green-300 transition-colors" size={24} />
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Timezone</div>
              <div className="text-white font-semibold text-lg">{selectedSite.timezone}</div>
            </div>
          </div>
        )}
        {selectedSite.climate && (
          <div className="card flex items-center gap-4 p-5 border border-gray-700/50 hover:border-yellow-500/50 hover:shadow-lg hover:shadow-yellow-500/10 transition-all duration-300 group">
            <div className="p-3 bg-yellow-500/10 rounded-xl group-hover:bg-yellow-500/20 transition-colors border border-yellow-500/20">
              <Settings className="text-yellow-400 group-hover:text-yellow-300 transition-colors" size={24} />
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Climate</div>
              <div className="text-white font-semibold text-lg">{selectedSite.climate}</div>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-700/50">
        <nav className="flex space-x-1">
          {(['overview', 'devices', 'alarms', 'rules', 'settings'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`relative py-3 px-6 font-medium text-sm transition-all duration-200 rounded-t-lg ${
                activeTab === tab
                  ? 'text-blue-400 bg-gray-800/50 border-t border-x border-gray-700/50'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/30'
              }`}
            >
              {activeTab === tab && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-blue-400"></span>
              )}
              <span className="relative z-10">{tab.charAt(0).toUpperCase() + tab.slice(1)}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'overview' && (
          <SiteOverviewTab
            selectedSite={selectedSite}
            stats={stats}
            devices={devices}
            deviceTimeSeries={deviceTimeSeries}
            loadingTimeSeries={loadingTimeSeries}
            selectedDevices={selectedDevices}
            setSelectedDevices={setSelectedDevices}
            selectedMetric={selectedMetric}
            setSelectedMetric={setSelectedMetric}
            timeRange={timeRange}
            setTimeRange={setTimeRange}
            interval={interval}
            setInterval={setInterval}
            availableMetrics={availableMetrics}
            siteId={siteId}
          />
        )}

        {activeTab === 'devices' && (
          <SiteDevicesTab
            devices={devices}
            onAddDevice={() => setShowAddDeviceModal(true)}
            onEditDevice={(device) => {
              setEditingDevice(device);
              setShowEditDeviceModal(true);
            }}
            onRemoveDevice={(device) => {
              setDeviceToRemove(device);
              setShowRemoveDeviceModal(true);
            }}
          />
        )}

        {activeTab === 'alarms' && siteId && (
          <SiteAlarmsTab siteId={siteId} />
        )}

        {activeTab === 'rules' && (
          <SiteRulesTab
            siteId={siteId}
            siteRules={siteRules}
            devices={devices}
            onAddRule={() => setShowAddRuleModal(true)}
            onEditRule={(rule) => {
              setEditingRule(rule);
              setShowEditRuleModal(true);
            }}
            onRefreshRules={() => {
              if (siteId) {
                fetchSiteRules(siteId);
              }
            }}
            onToast={addToast}
          />
        )}

        {activeTab === 'settings' && (
          <SiteSettingsTab />
        )}
      </div>

      {/* Modals */}
      {showAddDeviceModal && siteId && (
        <Modal
          isOpen={showAddDeviceModal}
          onClose={() => setShowAddDeviceModal(false)}
          title="Add Device to Site"
          size="md"
        >
          <AddDeviceForm
            siteId={siteId}
            onSuccess={() => {
              setShowAddDeviceModal(false);
              if (siteId) {
                fetchSiteDevices(siteId);
                // Refresh rules after adding device (device rules are auto-created)
                fetchSiteRules(siteId);
              }
            }}
            onCancel={() => setShowAddDeviceModal(false)}
          />
        </Modal>
      )}

      {showEditDeviceModal && editingDevice && (
        <Modal
          isOpen={showEditDeviceModal}
          onClose={() => {
            setShowEditDeviceModal(false);
            setEditingDevice(null);
          }}
          title="Edit Device"
          size="md"
        >
          <EditDeviceForm
            device={editingDevice}
            onSuccess={() => {
              setShowEditDeviceModal(false);
              setEditingDevice(null);
              if (siteId) {
                fetchSiteDevices(siteId);
              }
            }}
            onCancel={() => {
              setShowEditDeviceModal(false);
              setEditingDevice(null);
            }}
          />
        </Modal>
      )}

      {showAddRuleModal && siteId && (
        <Modal
          isOpen={showAddRuleModal}
          onClose={() => setShowAddRuleModal(false)}
          title="Add Rule"
          size="lg"
        >
          <AddRuleForm
            siteId={siteId}
            devices={devices}
            onSuccess={() => {
              setShowAddRuleModal(false);
              if (siteId) {
                fetchSiteRules(siteId);
              }
            }}
            onCancel={() => setShowAddRuleModal(false)}
          />
        </Modal>
      )}

      {showEditSiteModal && selectedSite && siteId && (
        <Modal
          isOpen={showEditSiteModal}
          onClose={() => setShowEditSiteModal(false)}
          title="Edit Site Information"
          size="lg"
        >
          <EditSiteForm
            site={selectedSite}
            onSave={async (siteData) => {
              if (!siteId) {
                addToast({
                  type: 'error',
                  message: 'Site ID is missing',
                });
                return;
              }

              try {
                await updateSiteInStore(siteId, siteData);
                addToast({
                  type: 'success',
                  message: 'Site updated successfully',
                });
                setShowEditSiteModal(false);
                if (siteId) {
                  fetchSiteStats(siteId).catch((err) => {
                    console.error('[SiteDetails] Error refreshing site stats:', err);
                  });
                  fetchSiteDevices(siteId).catch((err) => {
                    console.error('[SiteDetails] Error refreshing site devices:', err);
                  });
                }
              } catch (error: any) {
                const errorMessage = 
                  error?.response?.data?.message || 
                  error?.response?.data?.detail ||
                  error?.message || 
                  'Failed to update site. Please try again.';
                addToast({
                  type: 'error',
                  message: errorMessage,
                });
              }
            }}
            onCancel={() => {
              setShowEditSiteModal(false);
            }}
          />
        </Modal>
      )}

      {showEditRuleModal && siteId && editingRule && (
        <Modal
          isOpen={showEditRuleModal}
          onClose={() => {
            setShowEditRuleModal(false);
            setEditingRule(null);
          }}
          title="Edit Rule"
          size="lg"
        >
          <AddRuleForm
            siteId={siteId}
            devices={devices}
            initialRule={editingRule}
            onSuccess={async (ruleData) => {
              if (!ruleData) return;
              
              try {
                const response = await updateSiteRule(siteId, editingRule.id, ruleData);
                if (response.status === 'success') {
                  addToast(`Rule ${editingRule.id} updated successfully`, 'success');
                  setShowEditRuleModal(false);
                  setEditingRule(null);
                  if (siteId) {
                    fetchSiteRules(siteId);
                  }
                } else {
                  addToast(response.message || 'Failed to update rule', 'error');
                }
              } catch (error: any) {
                addToast(error?.response?.data?.message || error?.message || 'Failed to update rule', 'error');
              }
            }}
            onCancel={() => {
              setShowEditRuleModal(false);
              setEditingRule(null);
            }}
            onDelete={async (ruleId) => {
              try {
                const { deleteSiteRule } = await import('@/api/sites');
                const response = await deleteSiteRule(siteId, ruleId);
                if (response.status === 'success') {
                  addToast(`Rule ${ruleId} deleted successfully`, 'success');
                  setShowEditRuleModal(false);
                  setEditingRule(null);
                  if (siteId) {
                    fetchSiteRules(siteId);
                  }
                } else {
                  addToast(response.message || 'Failed to delete rule', 'error');
                }
              } catch (error: any) {
                addToast(error?.response?.data?.message || error?.message || 'Failed to delete rule', 'error');
              }
            }}
          />
        </Modal>
      )}

      {showDeleteModal && selectedSite && (
        <SiteDeleteModal
          isOpen={showDeleteModal}
          onClose={() => setShowDeleteModal(false)}
          onConfirm={handleDeleteSite}
          siteName={selectedSite.site_name}
          siteId={selectedSite.site_id}
          isDeleting={isDeleting}
        />
      )}

      {showRemoveDeviceModal && deviceToRemove && (
        <SiteRemoveDeviceModal
          isOpen={showRemoveDeviceModal}
          onClose={() => {
            setShowRemoveDeviceModal(false);
            setDeviceToRemove(null);
          }}
          onConfirm={handleRemoveDevice}
          device={deviceToRemove}
          isRemoving={isRemovingDevice}
        />
      )}

      {/* Diagnostic Result Modal - Using new professional component */}
      {showDiagnosticModal && diagnosticResult && (
        <Modal
          isOpen={showDiagnosticModal}
          onClose={() => {
            setShowDiagnosticModal(false);
            setDiagnosticResult(null);
          }}
          title=""
          size="xl"
        >
          <DiagnosticOutput 
            result={{ report: diagnosticResult }} 
            onClose={() => {
              setShowDiagnosticModal(false);
              setDiagnosticResult(null);
            }}
            variant="inline"
          />
        </Modal>
      )}
    </div>
  );
};
