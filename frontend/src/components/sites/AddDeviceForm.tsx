/**
 * Add Device Form Component
 * Form for adding a device to a site
 */

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DeviceType } from '@/config/constants';
import { useToastStore } from '@/store/useToastStore';
import { registerDevice } from '@/api/devices';

interface AddDeviceFormProps {
  siteId: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const AddDeviceForm = ({ siteId, onSuccess, onCancel }: AddDeviceFormProps) => {
  const { addToast } = useToastStore();
  const [formData, setFormData] = useState({
    device_id: '',
    device_type: 'BMS' as DeviceType,
    integration_name: '',
    brand: '',
    model: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const deviceData = {
        device_id: formData.device_id,
        device_type: formData.device_type,
        integration_name: formData.integration_name || undefined,
        metadata: {
          brand: formData.brand || undefined,
          model: formData.model || undefined,
          site_id: siteId, // Always associate with site when adding from site page
        },
      };
      
      const response = await registerDevice(deviceData);
      
      if (response.status === 'success') {
        addToast(`Device ${formData.device_id} added to site successfully`, 'success');
        if (onSuccess) {
          onSuccess();
        }
      } else {
        addToast(response.message || 'Failed to add device', 'error');
      }
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to add device';
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
          Device ID <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          name="device_id"
          value={formData.device_id}
          onChange={handleChange}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="BMS_001"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Device Type <span className="text-red-400">*</span>
        </label>
        <select
          name="device_type"
          value={formData.device_type}
          onChange={handleChange}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="BMS">BMS (Battery Management System)</option>
          <option value="PCS">PCS (Power Conversion System)</option>
          <option value="TMS">TMS (Thermal Management System)</option>
          <option value="UPS">UPS (Uninterruptible Power Supply)</option>
          <option value="EMS">EMS (Energy Management System)</option>
          <option value="OTHER">Other</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Brand/Manufacturer <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          name="brand"
          value={formData.brand}
          onChange={handleChange}
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Tesla, BYD, CATL, etc."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Model
        </label>
        <input
          type="text"
          name="model"
          value={formData.model}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Model number or name"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Integration Service Name
        </label>
        <input
          type="text"
          name="integration_name"
          value={formData.integration_name}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="bms-service-1"
        />
        <p className="text-xs text-gray-500 mt-1">Integration service that manages this device</p>
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
          {submitting ? 'Adding...' : 'Add Device'}
        </Button>
      </div>
    </form>
  );
};

