/**
 * Custom hook for SiteDetails page
 * Manages data fetching, state, and real-time updates
 */

import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useSiteStore } from '@/store/useSiteStore';
import { useDeviceStore } from '@/store/useDeviceStore';
import { useWebSocket, EventType } from '@/hooks/useWebSocket';
import { websocketEventManager } from '@/services/websocketEventManager';
import { useRealtime } from '@/hooks/useRealtime';
import { getDeviceTimeSeries, DeviceTimeSeriesDataPoint } from '@/api/metrics';
import { Device } from '@/types';

export interface UseSiteDetailsOptions {
  siteId: string | undefined;
}

export interface UseSiteDetailsReturn {
  // Site data
  selectedSite: any;
  stats: any;
  devices: Device[];
  siteRules: any;
  loading: boolean;
  error: string | null;
  
  // UI state
  activeTab: 'overview' | 'devices' | 'alarms' | 'reports' | 'rules' | 'settings';
  setActiveTab: (tab: 'overview' | 'devices' | 'alarms' | 'reports' | 'rules' | 'settings') => void;
  showAddDeviceModal: boolean;
  setShowAddDeviceModal: (show: boolean) => void;
  showAddRuleModal: boolean;
  setShowAddRuleModal: (show: boolean) => void;
  showEditRuleModal: boolean;
  setShowEditRuleModal: (show: boolean) => void;
  editingRule: any;
  setEditingRule: (rule: any) => void;
  showEditSiteModal: boolean;
  setShowEditSiteModal: (show: boolean) => void;
  showDeleteModal: boolean;
  setShowDeleteModal: (show: boolean) => void;
  isDeleting: boolean;
  setIsDeleting: (deleting: boolean) => void;
  showRemoveDeviceModal: boolean;
  setShowRemoveDeviceModal: (show: boolean) => void;
  deviceToRemove: Device | null;
  setDeviceToRemove: (device: Device | null) => void;
  isRemovingDevice: boolean;
  setIsRemovingDevice: (removing: boolean) => void;
  
  // Time series data
  deviceTimeSeries: DeviceTimeSeriesDataPoint[];
  loadingTimeSeries: boolean;
  selectedDevices: string[];
  setSelectedDevices: (devices: string[]) => void;
  selectedMetric: string;
  setSelectedMetric: (metric: string) => void;
  timeRange: string;
  setTimeRange: (range: string) => void;
  interval: string;
  setInterval: (interval: string) => void;
  availableMetrics: string[];
  
  // WebSocket
  connected: boolean;
  isSiteAlive: boolean;
  
  // Actions
  fetchSite: (siteId: string) => Promise<void>;
  fetchSiteStats: (siteId: string) => Promise<void>;
  fetchSiteDevices: (siteId: string) => Promise<void>;
  fetchSiteRules: (siteId: string) => Promise<void>;
  deleteSite: (siteId: string, deleteData: boolean) => Promise<void>;
  removeDevice: (deviceId: string, deleteData: boolean) => Promise<void>;
  updateSiteInStore: (siteId: string, siteData: any) => Promise<void>;
}

export const useSiteDetails = ({ siteId }: UseSiteDetailsOptions): UseSiteDetailsReturn => {
  const {
    selectedSite,
    siteStats,
    siteDevices,
    siteRules,
    loading,
    error,
    fetchSite,
    fetchSiteStats,
    fetchSiteDevices,
    fetchSiteRules,
    deleteSite: deleteSiteFromStore,
    setSelectedSite,
    updateSite: updateSiteInStore,
  } = useSiteStore();
  const { removeDevice: removeDeviceFromStore } = useDeviceStore();

  // UI state
  const [activeTab, setActiveTab] = useState<'overview' | 'devices' | 'alarms' | 'reports' | 'rules' | 'settings'>('overview');
  const [showAddDeviceModal, setShowAddDeviceModal] = useState(false);
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);
  const [showEditRuleModal, setShowEditRuleModal] = useState(false);
  const [editingRule, setEditingRule] = useState<any>(null);
  const [showEditSiteModal, setShowEditSiteModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showRemoveDeviceModal, setShowRemoveDeviceModal] = useState(false);
  const [deviceToRemove, setDeviceToRemove] = useState<Device | null>(null);
  const [isRemovingDevice, setIsRemovingDevice] = useState(false);

  // Time series state
  const [deviceTimeSeries, setDeviceTimeSeries] = useState<DeviceTimeSeriesDataPoint[]>([]);
  const [loadingTimeSeries, setLoadingTimeSeries] = useState(false);
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [timeRange, setTimeRange] = useState<string>('-24h');
  const [interval, setInterval] = useState<string>('1m');
  const previousTimeSeriesRef = useRef<DeviceTimeSeriesDataPoint[]>([]);
  const fetchTimeSeriesDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousMetricRef = useRef<string>(''); // Track previous metric to detect changes
  const previousQueryRef = useRef<{ devices: string; metric: string; timeRange: string; interval: string }>({ 
    devices: '', metric: '', timeRange: '', interval: '' 
  });

  // Get stats and devices
  const stats = siteStats[siteId!] || null;
  const devices = siteDevices[siteId!] || [];

  // Initial data fetch
  useEffect(() => {
    if (!siteId) {
      setSelectedSite(null);
      return;
    }

    const currentSiteId = useSiteStore.getState().selectedSite?.site_id;
    if (currentSiteId !== siteId) {
      setSelectedSite(null);
    }

    fetchSite(siteId).catch((err) => {
      console.error('[useSiteDetails] Error fetching site:', err);
    });
    fetchSiteStats(siteId).catch((err) => {
      console.error('[useSiteDetails] Error fetching site stats:', err);
    });
    fetchSiteDevices(siteId).catch((err) => {
      console.error('[useSiteDetails] Error fetching site devices:', err);
    });
    fetchSiteRules(siteId).catch((err) => {
      console.error('[useSiteDetails] Error fetching site rules:', err);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId]);

  // WebSocket for real-time updates
  const wsEvents = useMemo<EventType[]>(
    () => ['device_status_changed', 'device_added', 'device_removed', 'stats_updated', 'alarm_created', 'alarm_updated'],
    []
  );

  const { connected } = useWebSocket({
    enabled: true,
    events: wsEvents,
    onMessage: useCallback(() => {
      // Event manager will handle this
    }, []),
    onConnect: useCallback(() => {
      if (siteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
      }
    }, [siteId, fetchSiteDevices, fetchSiteStats]),
    onDisconnect: useCallback(() => {
      // Handle disconnect if needed
    }, []),
    onError: useCallback(() => {
      // Handle error if needed
    }, []),
  });

  // Subscribe to WebSocket events via event manager
  useEffect(() => {
    if (!siteId) return;

    const unsubscribeStatsUpdated = websocketEventManager.subscribe('stats_updated', () => {
      fetchSiteDevices(siteId);
      fetchSiteStats(siteId);
    });
    
    const unsubscribeDeviceRemoved = websocketEventManager.subscribe('device_removed', (data) => {
      const deviceSiteId = data?.site_id;
      if (deviceSiteId === siteId || !deviceSiteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
      }
    });
    
    const unsubscribeAlarmCreated = websocketEventManager.subscribe('alarm_created', (data) => {
      const alarmSiteId = data?.site_id;
      if (alarmSiteId === siteId || !alarmSiteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
      }
    });
    
    const unsubscribeAlarmUpdated = websocketEventManager.subscribe('alarm_updated', (data) => {
      const alarmSiteId = data?.site_id;
      if (alarmSiteId === siteId || !alarmSiteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
      }
    });
    
    const unsubscribeDeviceStatusChanged = websocketEventManager.subscribe('device_status_changed', (data) => {
      const deviceSiteId = data?.device?.metadata?.site_id || data?.site_id;
      if (deviceSiteId === siteId || !deviceSiteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
        
        const deviceId = data?.device_id || data?.device?.device_id;
        const isSelectedDevice = deviceId && selectedDevices.includes(deviceId);
        if (selectedDevices.length > 0 && selectedMetric && !loadingTimeSeries && isSelectedDevice) {
          if (fetchTimeSeriesDebounceRef.current) {
            clearTimeout(fetchTimeSeriesDebounceRef.current);
          }
          fetchTimeSeriesDebounceRef.current = setTimeout(() => {
            if (!loadingTimeSeries) {
              fetchDeviceTimeSeries();
            }
            fetchTimeSeriesDebounceRef.current = null;
          }, 1000);
        }
      }
    });
    
    const unsubscribeDeviceAdded = websocketEventManager.subscribe('device_added', (data) => {
      const deviceSiteId = data?.device?.metadata?.site_id || data?.site_id;
      if (deviceSiteId === siteId || !deviceSiteId) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
      }
    });

    return () => {
      unsubscribeStatsUpdated();
      unsubscribeDeviceRemoved();
      unsubscribeAlarmCreated();
      unsubscribeAlarmUpdated();
      unsubscribeDeviceStatusChanged();
      unsubscribeDeviceAdded();
    };
  }, [siteId, fetchSiteDevices, fetchSiteStats, selectedDevices, selectedMetric, loadingTimeSeries]);

  // Polling for real-time updates (only when WebSocket is not connected)
  useRealtime({
    enabled: !connected,
    interval: connected ? 0 : 30000,
    onUpdate: () => {
      if (siteId && !loading && !connected) {
        fetchSiteDevices(siteId);
        fetchSiteStats(siteId);
        if (selectedDevices.length > 0 && selectedMetric && !loadingTimeSeries) {
          if (fetchTimeSeriesDebounceRef.current) {
            clearTimeout(fetchTimeSeriesDebounceRef.current);
          }
          fetchTimeSeriesDebounceRef.current = setTimeout(() => {
            if (!loadingTimeSeries) {
              fetchDeviceTimeSeries();
            }
            fetchTimeSeriesDebounceRef.current = null;
          }, 2000);
        }
      }
    },
  });

  // Calculate site alive status based on device data, not just WebSocket connection
  // Site is considered alive if there are active devices, regardless of WebSocket connection
  const isSiteAlive = (stats?.devices?.by_status?.active > 0) || (devices?.some(device => device.status === 'active') ?? false);

  // Get available metrics from devices
  const availableMetrics = useMemo(() => {
    const metrics = new Set<string>();
    if (devices.some(d => d.device_type === 'BMS')) {
      metrics.add('soc');
      metrics.add('soh');
      metrics.add('cell_voltages');
      metrics.add('cell_voltages_mean');
      metrics.add('cell_voltages_max');
      metrics.add('cell_voltages_min');
      metrics.add('max_voltage');
      metrics.add('min_voltage');
      metrics.add('max_delta_v');
      metrics.add('voltage');
      metrics.add('current');
      metrics.add('temperature');
      metrics.add('max_temperature');
      metrics.add('min_temperature');
    }
    if (devices.some(d => d.device_type === 'PCS')) {
      metrics.add('active_power');
      metrics.add('reactive_power');
      metrics.add('voltage');
      metrics.add('current');
      metrics.add('frequency');
      metrics.add('efficiency');
    }
    if (devices.some(d => d.device_type === 'UPS')) {
      metrics.add('input_voltage');
      metrics.add('output_voltage');
      metrics.add('battery_voltage');
      metrics.add('temperature');
    }
    if (devices.some(d => d.device_type === 'TMS')) {
      metrics.add('ambient_temperature');
      metrics.add('coolant_temperature');
    }
    return Array.from(metrics).sort();
  }, [devices]);

  // Auto-select devices when devices are loaded
  useEffect(() => {
    if (devices.length > 0 && selectedDevices.length === 0) {
      const firstDevice = devices[0];
      console.log('[useSiteDetails] Auto-selecting first device:', firstDevice.device_id, 'type:', firstDevice.device_type);
      setSelectedDevices([firstDevice.device_id]);
      
      // Auto-select first metric if available
      if (availableMetrics.length > 0 && !selectedMetric) {
        const firstMetric = availableMetrics[0];
        console.log('[useSiteDetails] Auto-selecting first metric:', firstMetric);
        setSelectedMetric(firstMetric);
      } else if (availableMetrics.length === 0) {
        console.warn('[useSiteDetails] No available metrics for device type:', firstDevice.device_type);
      }
    }
    
    // Validate selected devices
    if (selectedDevices.length > 0) {
      const validDevices = selectedDevices.filter(deviceId => 
        devices.some(d => d.device_id === deviceId)
      );
      if (validDevices.length !== selectedDevices.length) {
        console.log('[useSiteDetails] Updating selected devices to valid ones:', validDevices);
        setSelectedDevices(validDevices);
      } else if (devices.length === 0 && selectedDevices.length > 0) {
        console.log('[useSiteDetails] Clearing selected devices (no devices available)');
        setSelectedDevices([]);
      }
    }
  }, [devices, selectedDevices.length, availableMetrics, selectedMetric]);

  // Fetch device time series data
  const fetchDeviceTimeSeries = useCallback(async () => {
    if (fetchTimeSeriesDebounceRef.current) {
      clearTimeout(fetchTimeSeriesDebounceRef.current);
      fetchTimeSeriesDebounceRef.current = null;
    }
    
    if (!siteId || selectedDevices.length === 0 || !selectedMetric) {
      console.log('[useSiteDetails] Skipping fetchDeviceTimeSeries - missing params:', {
        siteId,
        selectedDevices: selectedDevices.length,
        selectedMetric,
      });
      setDeviceTimeSeries([]);
      return;
    }
    
    console.log('[useSiteDetails] Fetching device time series:', {
      siteId,
      selectedDevices,
      selectedMetric,
      timeRange,
      interval,
    });
    
    const validDevices = selectedDevices.filter(deviceId => 
      devices.some(d => d.device_id === deviceId)
    );
    
    if (validDevices.length === 0) {
      setDeviceTimeSeries([]);
      previousTimeSeriesRef.current = [];
      return;
    }

    // Check if query parameters changed (device, metric, timeRange, or interval)
    const currentQuery = {
      devices: validDevices.sort().join(','),
      metric: selectedMetric,
      timeRange: timeRange,
      interval: interval,
    };
    const prevQuery = previousQueryRef.current;
    const queryChanged = 
      prevQuery.devices !== currentQuery.devices ||
      prevQuery.metric !== currentQuery.metric ||
      prevQuery.timeRange !== currentQuery.timeRange ||
      prevQuery.interval !== currentQuery.interval;

    // If query parameters changed (especially metric), clear previous data
    if (queryChanged) {
      previousTimeSeriesRef.current = [];
      previousMetricRef.current = selectedMetric;
      previousQueryRef.current = currentQuery;
    }

    // Only show loading for initial load or when query parameters change
    // For incremental updates, don't show loading to avoid flickering
    const shouldShowLoading = queryChanged || previousTimeSeriesRef.current.length === 0;
    if (shouldShowLoading) {
      setLoadingTimeSeries(true);
    }

    try {
      // For incremental updates, use 'since' parameter to only fetch new data
      // This reduces data transfer and processing time
      let sinceParam: string | undefined = undefined;
      let startTimeParam: string | undefined = timeRange; // Always use timeRange for initial query
      
      if (!queryChanged && previousTimeSeriesRef.current.length > 0) {
        // Get the last timestamp from previous data
        const lastPoint = previousTimeSeriesRef.current[previousTimeSeriesRef.current.length - 1];
        if (lastPoint?.timestamp) {
          // Use the last timestamp as 'since' to only get new data
          sinceParam = lastPoint.timestamp;
          // When using 'since', don't use start_time (backend will ignore it)
          startTimeParam = undefined;
        }
      }

      console.log('[useSiteDetails] Calling getDeviceTimeSeries with params:', {
        device_ids: validDevices,
        site_id: siteId,
        metric: selectedMetric,
        start_time: startTimeParam,
        interval: interval,
        since: sinceParam,
        queryChanged,
      });

      const response = await getDeviceTimeSeries({
        device_ids: validDevices,
        site_id: siteId,
        metric: selectedMetric,
        start_time: startTimeParam, // Always use timeRange for initial query
        interval: interval,
        since: sinceParam, // Use since for incremental updates
      });
      
      console.log('[useSiteDetails] Device time series response:', {
        status: response.status,
        dataCount: response.data?.time_series?.length || 0,
        total: response.data?.total || 0,
      });
      
      if (response.status === 'success' && response.data) {
        const newData = response.data.time_series || [];
        console.log('[useSiteDetails] Received time series data:', newData.length, 'points');
        
        const validData = newData.filter(point => {
          if (!point || !point.timestamp) return false;
          const timestamp = new Date(point.timestamp);
          if (isNaN(timestamp.getTime())) return false;
          const value = point.value;
          if (value === null || value === undefined || isNaN(value) || !isFinite(value)) return false;
          return true;
        });
        
        const sortedData = [...validData].sort((a, b) => {
          try {
            return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          } catch (e) {
            return 0;
          }
        });
        
        const prevData = previousTimeSeriesRef.current;
        
        // Handle incremental updates (when using 'since' parameter)
        if (!queryChanged && prevData.length > 0) {
          // This is an incremental update - check if we have new data
          if (sortedData.length === 0) {
            // No new data from incremental query - keep previous data
            // Don't update state to avoid unnecessary re-renders
            if (shouldShowLoading) {
              setLoadingTimeSeries(false);
            }
            return;
          }
          
          // We have new data - merge it with previous data
          const prevLastTimestamp = new Date(prevData[prevData.length - 1].timestamp).getTime();
          const newFirstTimestamp = new Date(sortedData[0].timestamp).getTime();
          const newLastTimestamp = new Date(sortedData[sortedData.length - 1].timestamp).getTime();
          
          if (newFirstTimestamp > prevLastTimestamp) {
            // New data is after previous data - append it
            const newPoints = sortedData.filter(point => {
              const pointTime = new Date(point.timestamp).getTime();
              return pointTime > prevLastTimestamp;
            });
            
            if (newPoints.length > 0) {
              const merged = [...prevData, ...newPoints];
              const windowSize = 2000;
              const windowed = merged.length > windowSize ? merged.slice(-windowSize) : merged;
              previousTimeSeriesRef.current = windowed;
              setDeviceTimeSeries(windowed);
              if (shouldShowLoading) {
                setLoadingTimeSeries(false);
              }
              return;
            }
          }
          
          if (newFirstTimestamp <= prevLastTimestamp && newLastTimestamp >= prevLastTimestamp) {
            // New data overlaps with previous data - append only new points
            const newPointsAfterLast = sortedData.filter(point => {
              const pointTime = new Date(point.timestamp).getTime();
              return pointTime > prevLastTimestamp;
            });
            
            if (newPointsAfterLast.length > 0) {
              const merged = [...prevData, ...newPointsAfterLast];
              const windowSize = 2000;
              const windowed = merged.length > windowSize ? merged.slice(-windowSize) : merged;
              previousTimeSeriesRef.current = windowed;
              setDeviceTimeSeries(windowed);
              if (shouldShowLoading) {
                setLoadingTimeSeries(false);
              }
              return;
            }
          }
          
          // Check if last point value changed (for real-time updates)
          const prevLast = prevData[prevData.length - 1];
          const newLast = sortedData[sortedData.length - 1];
          
          if (prevLast && newLast && 
              prevLast.timestamp === newLast.timestamp &&
              Math.abs((prevLast.value || 0) - (newLast.value || 0)) > 0.001) {
            // Only last point value changed - update just that point
            const updated = [...prevData];
            updated[updated.length - 1] = newLast;
            previousTimeSeriesRef.current = updated;
            setDeviceTimeSeries(updated);
            if (shouldShowLoading) {
              setLoadingTimeSeries(false);
            }
            return;
          }
          
          // No new data and no value changes - keep previous data
          if (shouldShowLoading) {
            setLoadingTimeSeries(false);
          }
          return;
        }
        
        // If query changed (metric, device, timeRange, or interval), replace with new data
        // Or if this is the initial load (prevData.length === 0)
        if (queryChanged || prevData.length === 0) {
          previousTimeSeriesRef.current = sortedData;
          setDeviceTimeSeries(sortedData);
          if (shouldShowLoading) {
            setLoadingTimeSeries(false);
          }
        } else {
          // Fallback: merge new points (shouldn't reach here in normal flow)
          const prevLastTimestamp = new Date(prevData[prevData.length - 1].timestamp).getTime();
          const newPoints = sortedData.filter(point => {
            const pointTime = new Date(point.timestamp).getTime();
            return pointTime > prevLastTimestamp;
          });
          
          if (newPoints.length > 0) {
            const merged = [...prevData, ...newPoints];
            const windowSize = 2000;
            const windowed = merged.length > windowSize ? merged.slice(-windowSize) : merged;
            previousTimeSeriesRef.current = windowed;
            setDeviceTimeSeries(windowed);
            if (shouldShowLoading) {
              setLoadingTimeSeries(false);
            }
          } else {
            // No new points - keep previous data instead of replacing with empty array
            // This prevents the "No data available" issue when incremental query returns empty
            if (shouldShowLoading) {
              setLoadingTimeSeries(false);
            }
            // Don't update state - keep previous data
          }
        }
      } else {
        console.warn('[useSiteDetails] API returned success but no data:', {
          status: response.status,
          message: response.message,
          data: response.data,
        });
        // Only clear data if this is an initial query (queryChanged = true)
        // For incremental queries, keep previous data
        if (queryChanged) {
          setDeviceTimeSeries([]);
          previousTimeSeriesRef.current = [];
        }
      }
    } catch (error) {
      console.error('[useSiteDetails] Error fetching device time series data:', error);
      console.error('[useSiteDetails] Error details:', {
        siteId,
        selectedDevices,
        selectedMetric,
        timeRange,
        interval,
        errorMessage: error instanceof Error ? error.message : String(error),
        errorStack: error instanceof Error ? error.stack : undefined,
      });
      setDeviceTimeSeries([]);
      previousTimeSeriesRef.current = [];
    } finally {
      // Only clear loading if we set it
      if (shouldShowLoading) {
        setLoadingTimeSeries(false);
      }
    }
  }, [siteId, selectedDevices, selectedMetric, timeRange, interval, devices]);

  // Fetch data when selection changes
  useEffect(() => {
    console.log('[useSiteDetails] Selection changed, checking if should fetch:', {
      selectedDevices: selectedDevices.length,
      selectedMetric,
      siteId,
      devicesCount: devices.length,
      availableMetricsCount: availableMetrics.length,
    });
    
    if (selectedDevices.length > 0 && selectedMetric && siteId) {
      console.log('[useSiteDetails] Triggering fetchDeviceTimeSeries');
      fetchDeviceTimeSeries();
    } else {
      console.log('[useSiteDetails] Clearing time series data - missing selection');
      setDeviceTimeSeries([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDevices, selectedMetric, timeRange, interval, siteId]);

  // Wrapper functions
  const deleteSite = useCallback(async (siteId: string, deleteData: boolean) => {
    await deleteSiteFromStore(siteId, deleteData);
  }, [deleteSiteFromStore]);

  const removeDevice = useCallback(async (deviceId: string, deleteData: boolean) => {
    await removeDeviceFromStore(deviceId, deleteData);
  }, [removeDeviceFromStore]);

  return {
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
    connected,
    isSiteAlive,
    
    // Actions
    fetchSite,
    fetchSiteStats,
    fetchSiteDevices,
    fetchSiteRules,
    deleteSite,
    removeDevice,
    updateSiteInStore,
  };
};

