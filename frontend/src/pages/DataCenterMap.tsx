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
  const [initialLoading, setInitialLoading] = useState(true);
  const navigate = useNavigate();

  // Initial load on mount - same pattern as Dashboard (full-page PageLoading until ready)
  useEffect(() => {
    const loadInitialData = async () => {
      setInitialLoading(true);
      const minDisplayMs = 300;
      const start = Date.now();
      try {
        await fetchSites();
      } finally {
        const elapsed = Date.now() - start;
        const remaining = Math.max(0, minDisplayMs - elapsed);
        setTimeout(() => setInitialLoading(false), remaining);
      }
    };
    loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // Show loading state during initial data fetch (same as Dashboard)
  if (initialLoading) {
    return <PageLoading message="Loading data center map..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1">Data Center Map</h1>
            <p className="text-gray-400 text-sm">View and manage data center sites</p>
          </div>
          <p className="text-gray-400 mt-1 text-sm sm:text-base">
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
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            variant="secondary"
            onClick={() => fetchSites()}
            disabled={loading}
            className="text-sm sm:text-base"
          >
            <RefreshCw size={16} className="sm:mr-2" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            variant="primary"
            onClick={() => setShowAddSiteModal(true)}
            className="text-sm sm:text-base"
          >
            <Plus size={16} className="sm:mr-2" />
            <span className="hidden sm:inline">Add Site</span>
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

