/**
 * Site Delete Modal Component
 * Confirmation modal for deleting a site
 */

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

interface SiteDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (deleteData: boolean) => Promise<void>;
  siteName: string;
  siteId: string;
  isDeleting: boolean;
}

export const SiteDeleteModal = ({
  isOpen,
  onClose,
  onConfirm,
  siteName,
  siteId,
  isDeleting,
}: SiteDeleteModalProps) => {
  const handleDelete = async () => {
    const selectedOption = (document.querySelector('input[name="deleteOption"]:checked') as HTMLInputElement)?.value;
    const deleteData = selectedOption === 'deleteData';
    await onConfirm(deleteData);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !isDeleting && onClose()}
      title="Delete Site"
      size="sm"
    >
      <div className="space-y-4">
        <p className="text-gray-300">
          Are you sure you want to delete site <strong className="text-white">{siteName}</strong> (ID: {siteId})?
        </p>
        
        <div className="space-y-2 mt-4">
          <label className="flex items-start gap-3 p-3 rounded-lg border border-gray-600/50 hover:border-gray-500/50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="deleteOption"
              value="preserveData"
              defaultChecked
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-300">Delete site configuration only</div>
              <div className="text-xs text-gray-400 mt-1">
                Site configuration and rules will be deleted. All historical data (alarms, diagnostics, device data) will be preserved.
              </div>
            </div>
          </label>
          
          <label className="flex items-start gap-3 p-3 rounded-lg border border-red-500/30 hover:border-red-500/50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="deleteOption"
              value="deleteData"
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-red-400">Delete site and all data</div>
              <div className="text-xs text-gray-400 mt-1">
                Site configuration, rules, and all historical data (alarms, diagnostics, device data) will be permanently deleted. This action cannot be undone.
              </div>
            </div>
          </label>
        </div>
        
        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-700/50">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isDeleting}
            className="hover:bg-gray-600/80 transition-all duration-200"
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            disabled={isDeleting}
            loading={isDeleting}
            className="hover:shadow-lg hover:shadow-red-500/20 transition-all duration-200"
          >
            {isDeleting ? 'Deleting...' : 'Delete Site'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};







