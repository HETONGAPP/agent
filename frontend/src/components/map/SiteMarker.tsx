/**
 * Site Marker Component
 * Custom marker for sites on the map with heartbeat animation on click
 */

import { useMemo, useState, useEffect, useRef } from 'react';
import { Marker, Popup } from 'react-leaflet';
import { DivIcon } from 'leaflet';
import { Site } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useNavigate } from 'react-router-dom';
import { useSiteStore } from '@/store/useSiteStore';
import { SiteStats } from '@/api/sites';

interface SiteMarkerProps {
  site: Site;
  onClick?: (site: Site) => void;
}

// Get pulse color based on alarm status
const getPulseColor = (status: string): { border: string; background: string } => {
  switch (status) {
    case 'critical':
      return { border: '#EF4444', background: 'rgba(239, 68, 68, 0.3)' }; // red-500
    case 'warning':
      return { border: '#EAB308', background: 'rgba(234, 179, 8, 0.3)' }; // yellow-500
    case 'active':
    case 'inactive':
    default:
      return { border: '#3B82F6', background: 'rgba(59, 130, 246, 0.3)' }; // blue-500 (default for all other statuses)
  }
};

// Get site status based on alarms
const getSiteStatus = (stats?: SiteStats): string => {
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

// Detect iOS (Safari often doesn't run CSS animations inside Leaflet's transformed pane)
const isIOS = typeof navigator !== 'undefined' && /iPad|iPhone|iPod/.test(navigator.userAgent);

// Heartbeat keyframes for Web Animations API (used on iOS where CSS animation fails)
const PULSE_KEYFRAMES: Keyframe[] = [
  { transform: 'translate(-50%, -50%) scale(1)', opacity: 0.8 },
  { transform: 'translate(-50%, -50%) scale(2.5)', opacity: 0.4 },
  { transform: 'translate(-50%, -50%) scale(3.5)', opacity: 0 },
];
const PULSE_OPTIONS: KeyframeAnimationOptions = { duration: 2000, easing: 'ease-out', fill: 'forwards' };

function runPulseAnimationJS(container: HTMLElement): void {
  const pulse1 = container.querySelector('.site-marker-pulse-1') as HTMLElement;
  const pulse2 = container.querySelector('.site-marker-pulse-2') as HTMLElement;
  const pulse3 = container.querySelector('.site-marker-pulse-3') as HTMLElement;
  if (!pulse1 || !pulse2 || !pulse3) return;
  pulse1.animate(PULSE_KEYFRAMES, { ...PULSE_OPTIONS, delay: 0 });
  pulse2.animate(PULSE_KEYFRAMES, { ...PULSE_OPTIONS, delay: 400 });
  pulse3.animate(PULSE_KEYFRAMES, { ...PULSE_OPTIONS, delay: 800 });
}

// Create custom icon with heartbeat animation support
const createSiteIcon = (
  isActive: boolean, 
  animationKey: number = 0,
  pulseColor: { border: string; background: string } = { border: '#3B82F6', background: 'rgba(59, 130, 246, 0.3)' }
) => {
  const iconColor = isActive ? '#3B82F6' : '#6B7280';
  
  return new DivIcon({
    html: `
      <div class="site-marker-container" data-animation-key="${animationKey}" data-pulse-color="${pulseColor.border}">
        <div class="site-marker-pulse site-marker-pulse-1" style="border-color: ${pulseColor.border}; background: ${pulseColor.background};"></div>
        <div class="site-marker-pulse site-marker-pulse-2" style="border-color: ${pulseColor.border}; background: ${pulseColor.background};"></div>
        <div class="site-marker-pulse site-marker-pulse-3" style="border-color: ${pulseColor.border}; background: ${pulseColor.background};"></div>
        <div class="site-marker-icon">
          <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" fill="${iconColor}" stroke="white" stroke-width="2"/>
            <circle cx="16" cy="16" r="6" fill="white"/>
          </svg>
        </div>
      </div>
    `,
    className: 'site-marker-wrapper',
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  });
};

export const SiteMarker = ({ site, onClick }: SiteMarkerProps) => {
  const navigate = useNavigate();
  const [animationKey, setAnimationKey] = useState(0);
  const markerRef = useRef<any>(null);
  const { siteStats, fetchSiteStats } = useSiteStore();
  
  const position: [number, number] = useMemo(() => {
    if (site.latitude && site.longitude) {
      return [site.latitude, site.longitude];
    }
    // Default position: North America (USA center)
    return [39.8283, -98.5795];
  }, [site.latitude, site.longitude]);

  // Fetch site stats on mount
  useEffect(() => {
    if (site.site_id) {
      fetchSiteStats(site.site_id);
    }
  }, [site.site_id, fetchSiteStats]);

  // Get site status and pulse color
  const stats = siteStats[site.site_id];
  const status = useMemo(() => getSiteStatus(stats), [stats]);
  const pulseColor = useMemo(() => getPulseColor(status), [status]);

  const icon = useMemo(() => {
    // Determine if site is active based on devices or other criteria
    const isActive = true; // TODO: Check site status
    return createSiteIcon(isActive, animationKey, pulseColor);
  }, [site, animationKey, pulseColor]);

  // Auto-trigger heartbeat animation every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setAnimationKey(prev => prev + 1);
    }, 5000); // 5 seconds

    return () => clearInterval(interval);
  }, []);

  // Restart animation when animationKey changes
  useEffect(() => {
    if (!markerRef.current) return;

    if (isIOS) {
      // iOS: run after Leaflet has updated the icon DOM
      const t = setTimeout(() => {
        const markerElement = markerRef.current?.getElement();
        const container = markerElement?.querySelector('.site-marker-container') as HTMLElement;
        if (container) runPulseAnimationJS(container);
      }, 50);
      return () => clearTimeout(t);
    }

    if (animationKey > 0) {
      const markerElement = markerRef.current.getElement();
      const container = markerElement?.querySelector('.site-marker-container') as HTMLElement;
      if (container) {
        const pulses = container.querySelectorAll('.site-marker-pulse');
        pulses.forEach((pulse: Element) => {
          const pulseEl = pulse as HTMLElement;
          pulseEl.style.animation = 'none';
          void pulseEl.offsetWidth;
          pulseEl.style.animation = '';
        });
      }
    }
  }, [animationKey]);

  // Set up click and popup event listeners, and on iOS start pulse animation once icon is in DOM
  useEffect(() => {
    if (!markerRef.current) return;
    const marker = markerRef.current;
    const leafletMarker = marker.leafletElement;

    if (leafletMarker) {
      const handleClick = () => setAnimationKey(prev => prev + 1);
      const handlePopupOpen = () => setAnimationKey(prev => prev + 1);
      leafletMarker.on('click', handleClick);
      leafletMarker.on('popupopen', handlePopupOpen);

      return () => {
        leafletMarker.off('click', handleClick);
        leafletMarker.off('popupopen', handlePopupOpen);
      };
    }
  }, []);

  const handleClick = () => {
    if (onClick) {
      onClick(site);
    } else {
      navigate(`/datacenter/sites/${site.site_id}`);
    }
  };

  return (
    <Marker 
      ref={markerRef}
      position={position} 
      icon={icon}
    >
      <Popup className="site-popup" closeButton={true}>
        <div className="p-5 min-w-[260px] max-w-[300px] relative">
          {/* Site Name Header */}
          <div className="mb-4 pr-8">
            <h3 className="font-bold text-xl text-white mb-1 tracking-tight leading-tight">
              {site.site_name}
            </h3>
            <span className="text-xs text-gray-400 font-mono bg-gray-800/50 px-2 py-1 rounded">
              {site.site_id}
            </span>
          </div>

          {/* Site Information */}
          <div className="space-y-2.5 text-sm mb-4">
            {site.location && (
              <div className="flex items-start gap-2.5">
                <span className="text-gray-400 font-medium min-w-[75px] text-xs">Location:</span>
                <span className="text-gray-200 leading-relaxed">{site.location}</span>
              </div>
            )}
            {site.timezone && (
              <div className="flex items-start gap-2.5">
                <span className="text-gray-400 font-medium min-w-[75px] text-xs">Timezone:</span>
                <span className="text-gray-200 text-xs">{site.timezone}</span>
              </div>
            )}
          </div>

          {/* Action Button */}
          <div className="pt-3 border-t border-white/10">
            <Button
              variant="primary"
              size="sm"
              onClick={handleClick}
              className="w-full font-medium"
            >
              View Details
            </Button>
          </div>
        </div>
      </Popup>
    </Marker>
  );
};

