/**
 * Site List Component
 * Displays a list of sites with their information and status
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Site } from '@/types';
import { SiteStats } from '@/api/sites';
import { useSiteStore } from '@/store/useSiteStore';
import { useToastStore } from '@/store/useToastStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useRealtime } from '@/hooks/useRealtime';
import { Badge } from '@/components/ui/Badge';
import { MapPin, Plug, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { REFRESH_INTERVALS } from '@/config/constants';

interface SiteListProps {
  sites: Site[];
  onSiteClick?: (site: Site) => void;
}

export const SiteList = ({ sites, onSiteClick }: SiteListProps) => {
  const navigate = useNavigate();
  const { siteStats, fetchSiteStats } = useSiteStore();

  // Fetch stats for all sites when component mounts or sites change
  // Use ref to prevent infinite loops
  const sitesRef = React.useRef<string[]>([]);
  useEffect(() => {
    const currentSiteIds = sites.map(s => s.site_id).filter(Boolean) as string[];
    const previousSiteIds = sitesRef.current;
    
    // Only fetch for new sites or if sites list changed
    if (currentSiteIds.length === 0) return;
    
    const newSiteIds = currentSiteIds.filter(id => !previousSiteIds.includes(id));
    const changed = currentSiteIds.length !== previousSiteIds.length || 
                    currentSiteIds.some(id => !previousSiteIds.includes(id));
    
    if (changed && newSiteIds.length > 0) {
      // Only fetch for new sites to avoid duplicate requests
      newSiteIds.forEach((siteId) => {
        fetchSiteStats(siteId);
      });
      sitesRef.current = currentSiteIds;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sites.length]); // Only depend on sites.length, not the full sites array

  // WebSocket for real-time updates
  const { connected } = useWebSocket({
    enabled: true,
    events: ['stats_updated', 'device_status_changed', 'device_added', 'device_removed'],
    onMessage: useCallback((message) => {
      // Refresh stats for all sites when stats are updated
      if (message.type === 'stats_updated' || message.type === 'device_status_changed') {
        sites.forEach((site) => {
          if (site.site_id) {
            fetchSiteStats(site.site_id);
          }
        });
      }
    }, [sites, fetchSiteStats]),
  });

  // Polling for real-time updates (always enabled as backup)
  useRealtime({
    enabled: true,
    interval: connected ? REFRESH_INTERVALS.SITE_LIST_WS : REFRESH_INTERVALS.SITE_LIST_POLL,
    onUpdate: () => {
      // Only fetch stats for a limited number of sites if there are many
      const sitesToPoll = sites.slice(0, 10); // Limit to first 10 sites for performance
      sitesToPoll.forEach((site) => {
        if (site.site_id) {
          fetchSiteStats(site.site_id);
        }
      });
    },
  });

  const handleSiteClick = (site: Site) => {
    if (onSiteClick) {
      onSiteClick(site);
    } else {
      navigate(`/datacenter/sites/${site.site_id}`);
    }
  };


  const getSiteStatus = (site: Site, stats?: SiteStats) => {
    if (!stats) return 'unknown';
    
    const criticalAlarms = stats.alarms?.by_severity?.Critical || 0;
    const totalAlarms = stats.alarms?.total || 0;
    const activeDevices = stats.devices?.by_status?.active || 0;
    const totalDevices = stats.devices?.total || 0;

    if (criticalAlarms > 0) return 'critical';
    if (totalAlarms > 0) return 'warning';
    if (totalDevices === 0) return 'inactive';
    if (activeDevices > 0) return 'active';
    return 'unknown';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle size={16} className="text-green-400" />;
      case 'critical':
        return <AlertTriangle size={16} className="text-red-400" />;
      case 'warning':
        return <AlertTriangle size={16} className="text-yellow-400" />;
      case 'inactive':
        return <XCircle size={16} className="text-gray-400" />;
      default:
        return <XCircle size={16} className="text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'border-green-500/50 bg-green-500/10';
      case 'critical':
        return 'border-red-500/50 bg-red-500/10';
      case 'warning':
        return 'border-yellow-500/50 bg-yellow-500/10';
      case 'inactive':
        return 'border-gray-500/50 bg-gray-500/10';
      default:
        return 'border-gray-600/50 bg-gray-600/10';
    }
  };

  if (sites.length === 0) {
    return (
      <div className="card">
        <div className="text-center py-12 text-gray-400">
          <p>No sites configured</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-lg sm:text-xl font-semibold text-white mb-3 sm:mb-4">Sites Overview</h2>
      <div className="space-y-2 sm:space-y-3">
        {sites.map((site) => {
          const stats = siteStats[site.site_id];
          const status = getSiteStatus(site, stats);
          const totalDevices = stats?.devices?.total || 0;
          const activeDevices = stats?.devices?.by_status?.active || 0;
          const totalAlarms = stats?.alarms?.total || 0;
          const criticalAlarms = stats?.alarms?.by_severity?.Critical || 0;

          return (
            <div
              key={site.site_id}
              onClick={() => handleSiteClick(site)}
              className={`p-3 sm:p-4 rounded-lg border-2 cursor-pointer transition-all hover:scale-[1.01] sm:hover:scale-[1.02] hover:shadow-lg ${getStatusColor(status)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 mb-2">
                    <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                      {getStatusIcon(status)}
                      <h3 className="text-base sm:text-lg font-semibold text-white truncate">{site.site_name}</h3>
                      {status !== 'unknown' && <Badge type="status" value={status} size="sm" />}
                      {status === 'unknown' && (
                        <span className="px-2 py-0.5 text-xs border border-gray-600/50 bg-gray-600/10 text-gray-400 rounded whitespace-nowrap">
                          Loading...
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 mt-2 sm:mt-3">
                    {/* Site ID and Location */}
                    <div className="space-y-1.5 sm:space-y-2">
                      <div className="flex items-center gap-2 text-xs sm:text-sm text-gray-400">
                        <span className="font-mono text-xs">ID:</span>
                        <span className="text-gray-300 truncate">{site.site_id}</span>
                      </div>
                      {site.location && (
                        <div className="flex items-center gap-2 text-xs sm:text-sm text-gray-400">
                          <MapPin size={12} className="sm:w-3.5 sm:h-3.5 flex-shrink-0" />
                          <span className="truncate">{site.location}</span>
                        </div>
                      )}
                      {site.timezone && (
                        <div className="text-xs text-gray-500">
                          {site.timezone}
                        </div>
                      )}
                    </div>

                    {/* Statistics */}
                    <div className="space-y-1.5 sm:space-y-2">
                      {stats ? (
                        <>
                          <div className="flex items-center gap-2 sm:gap-4 text-xs sm:text-sm">
                            <div className="flex items-center gap-1.5 sm:gap-2">
                              <Plug size={12} className="sm:w-3.5 sm:h-3.5 text-blue-400 flex-shrink-0" />
                              <span className="text-gray-300">
                                {activeDevices}/{totalDevices} Devices
                              </span>
                            </div>
                          </div>
                          
                          {totalAlarms > 0 && (
                            <div className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
                              <AlertTriangle 
                                size={12} 
                                className={`sm:w-3.5 sm:h-3.5 flex-shrink-0 ${criticalAlarms > 0 ? 'text-red-400' : 'text-yellow-400'}`}
                              />
                              <span className={`${criticalAlarms > 0 ? 'text-red-400' : 'text-yellow-400'}`}>
                                {totalAlarms} Alarm{totalAlarms !== 1 ? 's' : ''}
                                {criticalAlarms > 0 && ` (${criticalAlarms} Critical)`}
                              </span>
                            </div>
                          )}
                          
                          {totalAlarms === 0 && (
                            <div className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm text-green-400">
                              <CheckCircle size={12} className="sm:w-3.5 sm:h-3.5 flex-shrink-0" />
                              <span>No Alarms</span>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-xs sm:text-sm text-gray-500">
                          Loading statistics...
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
};

