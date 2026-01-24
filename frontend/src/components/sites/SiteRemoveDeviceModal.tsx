/**
 * Site Remove Device Modal Component
 * Confirmation modal for removing a device from a site
 */

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Device } from '@/types';

interface SiteRemoveDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (deleteData: boolean) => Promise<void>;
  device: Device | null;
  isRemoving: boolean;
}

export const SiteRemoveDeviceModal = ({
  isOpen,
  onClose,
  onConfirm,
  device,
  isRemoving,
}: SiteRemoveDeviceModalProps) => {
  if (!device) return null;

  const handleRemove = async () => {
    const selectedOption = (document.querySelector('input[name="removeOption"]:checked') as HTMLInputElement)?.value;
    const deleteData = selectedOption === 'deleteData';
    await onConfirm(deleteData);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !isRemoving && onClose()}
      title="Remove Device"
      size="sm"
    >
      <div className="space-y-4">
        <p className="text-gray-300">
          Are you sure you want to remove device <strong className="text-white">{device.device_id}</strong>?
        </p>
        
        <div className="bg-gray-900/50 rounded-lg p-4 space-y-3 border border-gray-700">
          <p className="text-sm font-medium text-gray-300 mb-2">Choose removal option:</p>
          
          <label className="flex items-start gap-3 p-3 rounded-lg border border-gray-700 hover:border-gray-600 cursor-pointer transition-colors">
            <input
              type="radio"
              name="removeOption"
              value="keepData"
              defaultChecked
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-white">Remove device only</div>
              <div className="text-xs text-gray-400 mt-1">
                Device will be unregistered, but all historical data (metrics, alarms, diagnostics) will be preserved.
              </div>
            </div>
          </label>
          
          <label className="flex items-start gap-3 p-3 rounded-lg border border-red-500/30 hover:border-red-500/50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="removeOption"
              value="deleteData"
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-red-400">Remove device and delete all data</div>
              <div className="text-xs text-gray-400 mt-1">
                Device will be unregistered and all historical data will be permanently deleted. This action cannot be undone.
              </div>
            </div>
          </label>
        </div>
        
        <div className="flex justify-end gap-2 mt-4">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isRemoving}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleRemove}
            disabled={isRemoving}
          >
            {isRemoving ? 'Removing...' : 'Remove Device'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};









