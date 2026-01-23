/**
 * Add Site Form Component
 * Form for adding a new site
 */

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { useSiteStore } from '@/store/useSiteStore';
import { useToastStore } from '@/store/useToastStore';
import { createSite } from '@/api/sites';
import { reverseGeocode, normalizeCountryName } from '@/utils/geocoding';

interface AddSiteFormProps {
  initialPosition?: { lat: number; lng: number } | null;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const AddSiteForm = ({ initialPosition, onSuccess, onCancel }: AddSiteFormProps) => {
  const { addToast } = useToastStore();
  const [formData, setFormData] = useState({
    site_id: '',
    site_name: '',
    location: '',
    country: 'United States',
    state: '',
    timezone: 'America/New_York',
    climate: '',
    latitude: initialPosition?.lat?.toString() || '',
    longitude: initialPosition?.lng?.toString() || '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [geocoding, setGeocoding] = useState(false);

  // Update coordinates and auto-fill country/state when initialPosition changes (from map click)
  useEffect(() => {
    if (initialPosition) {
      const lat = initialPosition.lat;
      const lng = initialPosition.lng;
      
      // Update coordinates immediately
      setFormData(prev => ({
        ...prev,
        latitude: lat.toString(),
        longitude: lng.toString(),
      }));

      // Perform reverse geocoding to get country and state/province
      setGeocoding(true);
      reverseGeocode(lat, lng)
        .then((result) => {
          if (result) {
            setFormData(prev => {
              // Store the current location value before updating
              const currentLocation = prev.location;
              
              return {
                ...prev,
                // Always update country and state from geocoding
                country: normalizeCountryName(result.country) || prev.country,
                state: result.state || result.province || prev.state,
                // Only auto-fill location if it's empty (preserve manual edits)
                // This allows users to manually edit location while country/state are auto-filled
                location: currentLocation || result.address || result.city || '',
                // Auto-fill timezone if available
                timezone: result.timezone || prev.timezone,
              };
            });
          }
        })
        .catch((error) => {
          console.error('[AddSiteForm] Error during reverse geocoding:', error);
          // Don't show error to user, just silently fail
        })
        .finally(() => {
          setGeocoding(false);
        });
    }
  }, [initialPosition]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    // Validate coordinates
    const lat = parseFloat(formData.latitude);
    const lng = parseFloat(formData.longitude);
    if (isNaN(lat) || isNaN(lng)) {
      addToast('Please provide valid latitude and longitude coordinates', 'error');
      setSubmitting(false);
      return;
    }
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      addToast('Latitude must be between -90 and 90, Longitude must be between -180 and 180', 'error');
      setSubmitting(false);
      return;
    }

    try {
      const siteData = {
        site_id: formData.site_id,
        site_name: formData.site_name,
        location: formData.location,
        country: formData.country,
        state: formData.state,
        latitude: lat,
        longitude: lng,
        timezone: formData.timezone,
        climate: formData.climate || undefined,
      };
      
      const response = await createSite(siteData);
      
      if (response.status === 'success') {
        addToast(`Site ${formData.site_id} created successfully`, 'success');
        if (onSuccess) {
          onSuccess();
        }
      } else {
        addToast(response.message || 'Failed to create site', 'error');
      }
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to create site';
      addToast(errorMessage, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Site ID <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          name="site_id"
          value={formData.site_id}
          onChange={handleChange}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="US_DC_001 or 1"
          pattern="[A-Za-z0-9_]+"
          title="Letters, numbers, and underscores allowed"
        />
        <p className="text-xs text-gray-500 mt-1">Unique identifier (e.g., US_DC_001, 1, SITE_001)</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Site Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          name="site_name"
          value={formData.site_name}
          onChange={handleChange}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="New York Data Center"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Location (City/Address)
          {geocoding && (
            <span className="ml-2 text-xs text-blue-400">(Auto-detecting...)</span>
          )}
        </label>
        <input
          type="text"
          name="location"
          value={formData.location}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="New York, NY"
        />
        <p className="text-xs text-gray-500 mt-1">
          {initialPosition 
            ? "Auto-filled from map click. You can edit this field manually."
            : "Click on map to auto-fill, or enter manually"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Country
            {geocoding && (
              <span className="ml-2 text-xs text-blue-400">(Detecting...)</span>
            )}
          </label>
          <select
            name="country"
            value={formData.country}
            onChange={handleChange}
            disabled={geocoding}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="United States">United States</option>
            <option value="Canada">Canada</option>
            <option value="Mexico">Mexico</option>
            <option value="Other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            State/Province
            {geocoding && (
              <span className="ml-2 text-xs text-blue-400">(Detecting...)</span>
            )}
          </label>
          <input
            type="text"
            name="state"
            value={formData.state}
            onChange={handleChange}
            disabled={geocoding}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            placeholder="NY, CA, TX, etc."
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Latitude <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            name="latitude"
            value={formData.latitude}
            onChange={handleChange}
            step="any"
            min="-90"
            max="90"
            required
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="40.7128"
          />
          <p className="text-xs text-gray-500 mt-1">Click on map to set coordinates</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Longitude <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            name="longitude"
            value={formData.longitude}
            onChange={handleChange}
            step="any"
            min="-180"
            max="180"
            required
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="-74.0060"
          />
          <p className="text-xs text-gray-500 mt-1">Click on map to set coordinates</p>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Timezone
          {geocoding && (
            <span className="ml-2 text-xs text-blue-400">(Detecting...)</span>
          )}
        </label>
        <select
          name="timezone"
          value={formData.timezone}
          onChange={handleChange}
          disabled={geocoding}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <optgroup label="US Timezones">
            <option value="America/New_York">Eastern (America/New_York)</option>
            <option value="America/Chicago">Central (America/Chicago)</option>
            <option value="America/Denver">Mountain (America/Denver)</option>
            <option value="America/Los_Angeles">Pacific (America/Los_Angeles)</option>
            <option value="America/Phoenix">Arizona (America/Phoenix)</option>
            <option value="America/Anchorage">Alaska (America/Anchorage)</option>
            <option value="Pacific/Honolulu">Hawaii (Pacific/Honolulu)</option>
          </optgroup>
          <optgroup label="Canada Timezones">
            <option value="America/Toronto">Eastern (America/Toronto)</option>
            <option value="America/Winnipeg">Central (America/Winnipeg)</option>
            <option value="America/Edmonton">Mountain (America/Edmonton)</option>
            <option value="America/Vancouver">Pacific (America/Vancouver)</option>
          </optgroup>
          <optgroup label="Other">
            <option value="UTC">UTC</option>
            <option value="America/Mexico_City">Mexico (America/Mexico_City)</option>
          </optgroup>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Climate (Optional)
        </label>
        <select
          name="climate"
          value={formData.climate}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select climate type...</option>
          <option value="Continental">Continental</option>
          <option value="Temperate">Temperate</option>
          <option value="Subtropical">Subtropical</option>
          <option value="Desert">Desert</option>
          <option value="Mediterranean">Mediterranean</option>
          <option value="Maritime">Maritime</option>
          <option value="Arctic/Subarctic">Arctic/Subarctic</option>
        </select>
        <p className="text-xs text-gray-500 mt-1">Used for temperature threshold adjustments</p>
      </div>

      <div className="flex justify-end gap-2 pt-4">
        <Button
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          disabled={submitting}
        >
          {submitting ? 'Creating...' : 'Create Site'}
        </Button>
      </div>
    </form>
  );
};

