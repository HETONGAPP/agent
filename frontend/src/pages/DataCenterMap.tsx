/**
 * Data Center Map Page
 * Main page showing map with all sites
 */

import React, { useState, useEffect } from 'react';
import { DataCenterMap } from '@/components/map/DataCenterMap';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { AddSiteForm } from '@/components/sites/AddSiteForm';
import { SiteList } from '@/components/sites/SiteList';
import { Site } from '@/types';
import { useSiteStore } from '@/store/useSiteStore';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw } from 'lucide-react';
import { PageLoading } from '@/components/ui/PageLoading';

export const DataCenterMapPage = () => {
  const { sites, loading, fetchSites, error } = useSiteStore(); // Sites are preloaded in App.tsx
  const [showAddSiteModal, setShowAddSiteModal] = useState(false);
  const [clickedPosition, setClickedPosition] = useState<{ lat: number; lng: number } | null>(null);
  const navigate = useNavigate();

  // Sites are preloaded in App.tsx, but refresh if needed (e.g., after adding a site)
  // Only fetch if sites list is empty (fallback) - use ref to prevent infinite loops
  const hasFetchedRef = React.useRef(false);
  useEffect(() => {
    if (sites.length === 0 && !loading && !hasFetchedRef.current) {
      console.log('[DataCenterMapPage] Sites list empty, fetching...');
      fetchSites();
      hasFetchedRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Debug: Log sites when they change
  useEffect(() => {
    console.log('[DataCenterMapPage] Sites updated:', sites.length, 'sites');
    if (sites.length > 0) {
      console.log('[DataCenterMapPage] Site details:', sites);
    }
  }, [sites]);

  const handleSiteClick = (site: Site) => {
    navigate(`/datacenter/sites/${site.site_id}`);
  };

  const handleMapClick = (lat: number, lng: number) => {
    setClickedPosition({ lat, lng });
    setShowAddSiteModal(true);
  };

  const handleAddSiteSuccess = () => {
    setShowAddSiteModal(false);
    setClickedPosition(null);
    fetchSites();
  };

  // Show loading state during initial data fetch
  if (loading && sites.length === 0) {
    return <PageLoading message="Loading data center map..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div>
            <h1 className="text-3xl font-bold text-white mb-1">Data Center Map</h1>
            <p className="text-gray-400 text-sm">View and manage data center sites</p>
          </div>
          <p className="text-gray-400 mt-1">
            {loading ? 'Loading sites...' : `${sites.length} site${sites.length !== 1 ? 's' : ''} configured`}
            {sites.length > 0 && (
              <span className="ml-2 text-green-400">
                ({sites.filter(s => s.latitude && s.longitude).length} with coordinates)
              </span>
            )}
          </p>
          {error && (
            <p className="text-red-400 mt-1 text-sm">Error: {error}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => fetchSites()}
            disabled={loading}
          >
            <RefreshCw size={16} className="mr-2" />
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => setShowAddSiteModal(true)}
          >
            <Plus size={16} className="mr-2" />
            Add Site
          </Button>
        </div>
      </div>

      {/* Map View */}
      <div className="card p-0 overflow-hidden">
        <DataCenterMap
          onSiteClick={handleSiteClick}
          onMapClick={handleMapClick}
          height="500px"
        />
      </div>

      {/* Site List */}
      <SiteList sites={sites} onSiteClick={handleSiteClick} />

      {/* Add Site Modal */}
      {showAddSiteModal && (
        <Modal
          isOpen={showAddSiteModal}
          onClose={() => {
            setShowAddSiteModal(false);
            setClickedPosition(null);
          }}
          title="Add New Site"
        >
          <AddSiteForm
            initialPosition={clickedPosition}
            onSuccess={handleAddSiteSuccess}
            onCancel={() => {
              setShowAddSiteModal(false);
              setClickedPosition(null);
            }}
          />
        </Modal>
      )}
    </div>
  );
};

