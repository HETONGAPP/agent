/**
 * Data Center Map Component
 * Main map view for displaying sites
 */

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, useMapEvents, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './map-styles.css';
import { Site } from '@/types';
import { SiteMarker } from './SiteMarker';
import { useSiteStore } from '@/store/useSiteStore';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

// Fix for default marker icons in react-leaflet
import L from 'leaflet';

// Create default icon using inline SVG to avoid import issues
const DefaultIcon = L.icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
      <path fill="#3388ff" stroke="#fff" stroke-width="2" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 8.5 12.5 28.5 12.5 28.5S25 21 25 12.5C25 5.6 19.4 0 12.5 0z"/>
      <circle cx="12.5" cy="12.5" r="5" fill="#fff"/>
    </svg>
  `),
  shadowUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg width="41" height="41" viewBox="0 0 41 41" xmlns="http://www.w3.org/2000/svg">
      <ellipse cx="20.5" cy="20.5" rx="20" ry="20" fill="#000" opacity="0.3"/>
    </svg>
  `),
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [0, -41],
  shadowSize: [41, 41],
  shadowAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

interface DataCenterMapProps {
  onSiteClick?: (site: Site) => void;
  onMapClick?: (lat: number, lng: number) => void;
  height?: string;
}

// Component to handle map click events
function MapClickHandler({ onMapClick }: { onMapClick?: (lat: number, lng: number) => void }) {
  useMapEvents({
    click: (e) => {
      if (onMapClick) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

// Component to enforce zoom limits - prevent zoom out beyond minZoom
function ZoomLimiter({ minZoom, maxZoom }: { minZoom: number; maxZoom: number }) {
  const map = useMap();
  
  useEffect(() => {
    // Ensure map size matches container on mount and resize
    const updateMapSize = () => {
      setTimeout(() => {
        map.invalidateSize();
      }, 100);
    };
    
    updateMapSize();
    window.addEventListener('resize', updateMapSize);
    
    // Set zoom limits on map options
    map.setMinZoom(minZoom);
    map.setMaxZoom(maxZoom);

    const handleZoom = () => {
      const currentZoom = map.getZoom();
      if (currentZoom < minZoom) {
        map.setZoom(minZoom, { animate: false });
      } else if (currentZoom > maxZoom) {
        map.setZoom(maxZoom, { animate: false });
      }
    };

    // Intercept wheel events to prevent zoom beyond limits
    const handleWheel = (e: WheelEvent) => {
      const currentZoom = map.getZoom();
      
      // Check if zooming out (deltaY > 0)
      if (e.deltaY > 0) {
        // Prevent if already at or below minZoom
        // This is a fixed zoom level limit to prevent excessive zoom out
        if (currentZoom <= minZoom) {
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
          return false;
        }
      }
      
      // Check if zooming in (deltaY < 0) and already at maxZoom
      if (e.deltaY < 0 && currentZoom >= maxZoom) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        return false;
      }
    };

    // Listen to zoom events
    map.on('zoom', handleZoom);
    map.on('zoomend', handleZoom);
    
    // Intercept wheel events on the map container
    const mapContainer = map.getContainer();
    mapContainer.addEventListener('wheel', handleWheel, { passive: false, capture: true });

    return () => {
      window.removeEventListener('resize', updateMapSize);
      map.off('zoom', handleZoom);
      map.off('zoomend', handleZoom);
      mapContainer.removeEventListener('wheel', handleWheel, { capture: true } as EventListenerOptions);
    };
  }, [map, minZoom, maxZoom]);

  return null;
}

export const DataCenterMap = ({ onSiteClick, onMapClick, height = '600px' }: DataCenterMapProps) => {
  const { sites, loading, fetchSites } = useSiteStore();
  // Default center: North America (USA center)
  const [mapCenter, setMapCenter] = useState<[number, number]>([45.0, -100.0]); // Center of North America
  const [mapZoom, setMapZoom] = useState(4); // Zoom level to cover entire North America

  useEffect(() => {
    console.log('[DataCenterMap] Component mounted, fetching sites...');
    fetchSites();
  }, [fetchSites]);

  // Debug: Log sites when they change
  useEffect(() => {
    console.log('[DataCenterMap] Sites updated:', sites.length, 'sites');
    if (sites.length > 0) {
      console.log('[DataCenterMap] Site details:', sites.map(s => ({ 
        id: s.site_id, 
        name: s.site_name, 
        lat: s.latitude, 
        lng: s.longitude,
        hasCoords: !!(s.latitude && s.longitude)
      })));
    }
  }, [sites]);

  // Calculate map center based on sites (if sites exist, use their average)
  useEffect(() => {
    if (sites.length > 0) {
      const sitesWithCoords = sites.filter(s => s.latitude && s.longitude);
      if (sitesWithCoords.length > 0) {
        const avgLat = sitesWithCoords.reduce((sum, s) => sum + (s.latitude || 0), 0) / sitesWithCoords.length;
        const avgLng = sitesWithCoords.reduce((sum, s) => sum + (s.longitude || 0), 0) / sitesWithCoords.length;
        setMapCenter([avgLat, avgLng]);
        // Adjust zoom based on number of sites
        if (sitesWithCoords.length === 1) {
          setMapZoom(6);
        } else if (sitesWithCoords.length < 5) {
          setMapZoom(5);
        } else {
          setMapZoom(4);
        }
      }
    }
  }, [sites]);

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <LoadingSpinner />
      </div>
    );
  }

  // World map bounds - limit scrolling to prevent infinite panning
  // Latitude: -85 to 85 (tiles don't work well at poles)
  // Longitude: -180 to 180 (full world width)
  const worldBounds: [[number, number], [number, number]] = [
    [-85, -180], // Southwest corner
    [85, 180],   // Northeast corner
  ];

  return (
    <div className="w-full rounded-lg overflow-hidden border border-gray-700 bg-gray-900" style={{ height, position: 'relative' }}>
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        minZoom={3}
        maxZoom={18}
        maxBounds={worldBounds}
        maxBoundsViscosity={1.0}
        worldCopyJump={false}
        style={{ height: '100%', width: '100%', backgroundColor: '#1f2937', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          noWrap={true}
        />
        <ZoomLimiter minZoom={3} maxZoom={18} />
        <MapClickHandler onMapClick={onMapClick} />
        {sites.length > 0 ? (
          sites.map((site) => {
            console.log('[DataCenterMap] Rendering marker for site:', site.site_id, 'at', site.latitude, site.longitude);
            return (
              <SiteMarker
                key={site.site_id}
                site={site}
                onClick={onSiteClick}
              />
            );
          })
        ) : (
          <div style={{ position: 'absolute', top: '10px', left: '10px', zIndex: 1000, background: 'rgba(0,0,0,0.7)', color: 'white', padding: '10px', borderRadius: '5px' }}>
            No sites to display
          </div>
        )}
      </MapContainer>
    </div>
  );
};

