/**
 * Edit Site Form Component
 * Form for editing site information
 */

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Site } from '@/api/sites';

interface EditSiteFormProps {
  site: Site;
  onSave: (siteData: Partial<Site>) => Promise<void>;
  onCancel: () => void;
}

export const EditSiteForm = ({ site, onSave, onCancel }: EditSiteFormProps) => {
  const [formData, setFormData] = useState<Partial<Site>>({
    site_name: site.site_name || '',
    location: site.location || '',
    country: (site as any).country || 'United States',
    state: (site as any).state || '',
    timezone: site.timezone || 'America/New_York',
    climate: site.climate || '',
    latitude: site.latitude || undefined,
    longitude: site.longitude || undefined,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setFormData({
      site_name: site.site_name || '',
      location: site.location || '',
      country: (site as any).country || 'United States',
      state: (site as any).state || '',
      timezone: site.timezone || 'America/New_York',
      climate: site.climate || '',
      latitude: site.latitude || undefined,
      longitude: site.longitude || undefined,
    });
  }, [site]);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.site_name || formData.site_name.trim().length === 0) {
      newErrors.site_name = 'Site name is required';
    }

    // Validate coordinates if provided
    if (formData.latitude !== undefined && formData.latitude !== null && formData.latitude !== '') {
      const lat = Number(formData.latitude);
      if (isNaN(lat) || lat < -90 || lat > 90) {
        newErrors.latitude = 'Latitude must be between -90 and 90';
      }
    }

    if (formData.longitude !== undefined && formData.longitude !== null && formData.longitude !== '') {
      const lng = Number(formData.longitude);
      if (isNaN(lng) || lng < -180 || lng > 180) {
        newErrors.longitude = 'Longitude must be between -180 and 180';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!validate()) {
      return;
    }

    setIsSubmitting(true);
    try {
      // Prepare data for submission
      const submitData: Partial<Site> = {
        site_name: formData.site_name?.trim(),
        location: formData.location?.trim() || undefined,
        country: formData.country || undefined,
        state: formData.state?.trim() || undefined,
        timezone: formData.timezone?.trim() || 'America/New_York',
        climate: formData.climate?.trim() || undefined,
        latitude: formData.latitude !== undefined && formData.latitude !== null && formData.latitude !== '' 
          ? Number(formData.latitude) 
          : undefined,
        longitude: formData.longitude !== undefined && formData.longitude !== null && formData.longitude !== '' 
          ? Number(formData.longitude) 
          : undefined,
      };

      // Remove undefined values
      Object.keys(submitData).forEach(key => {
        if (submitData[key as keyof Site] === undefined) {
          delete submitData[key as keyof Site];
        }
      });

      console.log('[EditSiteForm] Submitting data:', submitData);
      await onSave(submitData);
    } catch (error) {
      console.error('[EditSiteForm] Error saving site:', error);
      // Don't re-throw, let parent handle it
      // The error is already handled in the parent component
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Site Name */}
      <div>
        <label htmlFor="site_name" className="block text-sm font-medium text-gray-300 mb-2">
          Site Name <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          id="site_name"
          value={formData.site_name || ''}
          onChange={(e) => setFormData({ ...formData, site_name: e.target.value })}
          className={`w-full px-4 py-2 bg-gray-800 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
            errors.site_name ? 'border-red-500' : 'border-gray-700'
          }`}
          placeholder="Enter site name"
          required
        />
        {errors.site_name && (
          <p className="mt-1 text-sm text-red-400">{errors.site_name}</p>
        )}
      </div>

      {/* Location */}
      <div>
        <label htmlFor="location" className="block text-sm font-medium text-gray-300 mb-2">
          Location (City/Address)
        </label>
        <input
          type="text"
          id="location"
          value={formData.location || ''}
          onChange={(e) => setFormData({ ...formData, location: e.target.value })}
          className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="New York, NY"
        />
      </div>

      {/* Country and State */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="country" className="block text-sm font-medium text-gray-300 mb-2">
            Country
          </label>
          <select
            id="country"
            value={formData.country || 'United States'}
            onChange={(e) => setFormData({ ...formData, country: e.target.value })}
            className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="United States">United States</option>
            <option value="Canada">Canada</option>
            <option value="Mexico">Mexico</option>
            <option value="Other">Other</option>
          </select>
        </div>
        <div>
          <label htmlFor="state" className="block text-sm font-medium text-gray-300 mb-2">
            State/Province
          </label>
          <input
            type="text"
            id="state"
            value={formData.state || ''}
            onChange={(e) => setFormData({ ...formData, state: e.target.value })}
            className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="NY, CA, TX, etc."
          />
        </div>
      </div>

      {/* Timezone */}
      <div>
        <label htmlFor="timezone" className="block text-sm font-medium text-gray-300 mb-2">
          Timezone
        </label>
        <select
          id="timezone"
          value={formData.timezone || 'America/New_York'}
          onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
          className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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

      {/* Climate */}
      <div>
        <label htmlFor="climate" className="block text-sm font-medium text-gray-300 mb-2">
          Climate (Optional)
        </label>
        <select
          id="climate"
          value={formData.climate || ''}
          onChange={(e) => setFormData({ ...formData, climate: e.target.value })}
          className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
        <p className="mt-1 text-xs text-gray-500">Used for temperature threshold adjustments</p>
      </div>

      {/* Coordinates */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="latitude" className="block text-sm font-medium text-gray-300 mb-2">
            Latitude <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            id="latitude"
            name="latitude"
            step="any"
            min="-90"
            max="90"
            required
            value={formData.latitude ?? ''}
            onChange={(e) => setFormData({ ...formData, latitude: e.target.value ? parseFloat(e.target.value) : undefined })}
            className={`w-full px-4 py-2 bg-gray-800 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
              errors.latitude ? 'border-red-500' : 'border-gray-700'
            }`}
            placeholder="40.7128"
          />
          {errors.latitude && (
            <p className="mt-1 text-sm text-red-400">{errors.latitude}</p>
          )}
          <p className="mt-1 text-xs text-gray-500">Click on map to set coordinates</p>
        </div>

        <div>
          <label htmlFor="longitude" className="block text-sm font-medium text-gray-300 mb-2">
            Longitude <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            id="longitude"
            name="longitude"
            step="any"
            min="-180"
            max="180"
            required
            value={formData.longitude ?? ''}
            onChange={(e) => setFormData({ ...formData, longitude: e.target.value ? parseFloat(e.target.value) : undefined })}
            className={`w-full px-4 py-2 bg-gray-800 border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
              errors.longitude ? 'border-red-500' : 'border-gray-700'
            }`}
            placeholder="-74.0060"
          />
          {errors.longitude && (
            <p className="mt-1 text-sm text-red-400">{errors.longitude}</p>
          )}
          <p className="mt-1 text-xs text-gray-500">Click on map to set coordinates</p>
        </div>
      </div>

      {/* Site ID (read-only) */}
      <div>
        <label htmlFor="site_id" className="block text-sm font-medium text-gray-300 mb-2">
          Site ID
        </label>
        <input
          type="text"
          id="site_id"
          value={site.site_id}
          disabled
          className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-400 cursor-not-allowed"
        />
        <p className="mt-1 text-xs text-gray-500">Site ID cannot be changed</p>
      </div>

      {/* Form Actions */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-700">
        <Button
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </form>
  );
};

