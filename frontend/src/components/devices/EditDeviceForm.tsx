/**
 * Edit Device Form Component
 * Form for editing device information
 */

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { DeviceType } from '@/config/constants';
import { useToastStore } from '@/store/useToastStore';
import { updateDevice } from '@/api/devices';
import { Device } from '@/types';

interface EditDeviceFormProps {
  device: Device;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export const EditDeviceForm = ({ device, onSuccess, onCancel }: EditDeviceFormProps) => {
  const { addToast } = useToastStore();
  const [formData, setFormData] = useState({
    integration_name: device.integration_name || '',
    brand: (device.metadata as any)?.brand || '',
    model: (device.metadata as any)?.model || '',
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Update form data when device changes
    setFormData({
      integration_name: device.integration_name || '',
      brand: (device.metadata as any)?.brand || '',
      model: (device.metadata as any)?.model || '',
    });
  }, [device]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const deviceData = {
        integration_name: formData.integration_name || undefined,
        metadata: {
          ...(device.metadata || {}),
          brand: formData.brand || undefined,
          model: formData.model || undefined,
        },
      };
      
      const response = await updateDevice(device.device_id, deviceData);
      
      if (response.status === 'success') {
        addToast(`Device ${device.device_id} updated successfully`, 'success');
        if (onSuccess) {
          onSuccess();
        }
      } else {
        addToast(response.message || 'Failed to update device', 'error');
      }
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to update device';
      addToast(errorMessage, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Device ID
        </label>
        <input
          type="text"
          value={device.device_id}
          disabled
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 cursor-not-allowed"
        />
        <p className="text-xs text-gray-500 mt-1">Device ID cannot be changed</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Device Type
        </label>
        <input
          type="text"
          value={device.device_type}
          disabled
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-400 cursor-not-allowed"
        />
        <p className="text-xs text-gray-500 mt-1">Device type cannot be changed</p>
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
        <p className="text-xs text-gray-500 mt-1">Integration service that manages this device (optional)</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Brand/Manufacturer
        </label>
        <input
          type="text"
          name="brand"
          value={formData.brand}
          onChange={handleChange}
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
          {submitting ? 'Updating...' : 'Update Device'}
        </Button>
      </div>
    </form>
  );
};








