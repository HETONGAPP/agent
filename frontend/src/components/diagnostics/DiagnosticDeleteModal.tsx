/**
 * Diagnostic Delete Modal Component
 * Confirmation modal for deleting a diagnostic report
 */

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Diagnostic } from '@/types';

interface DiagnosticDeleteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  diagnostic: Diagnostic | null;
  isDeleting: boolean;
}

export const DiagnosticDeleteModal = ({
  isOpen,
  onClose,
  onConfirm,
  diagnostic,
  isDeleting,
}: DiagnosticDeleteModalProps) => {
  if (!diagnostic) return null;

  const handleDelete = async () => {
    await onConfirm();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !isDeleting && onClose()}
      title="Remove Diagnostic"
      size="sm"
    >
      <div className="space-y-4">
        <p className="text-gray-300">
          Are you sure you want to remove diagnostic report for alarm <strong className="text-white">{diagnostic.alarm_id}</strong>?
        </p>
        
        <div className="bg-gray-900/50 rounded-lg p-4 space-y-3 border border-gray-700">
          <p className="text-sm font-medium text-gray-300 mb-2">This will permanently delete:</p>
          <ul className="text-xs text-gray-400 space-y-1 list-disc list-inside">
            <li>Diagnostic report from database</li>
            <li>Cached diagnostic data</li>
            <li>All associated diagnostic information</li>
          </ul>
          <p className="text-xs text-red-400 mt-2 font-medium">
            This action cannot be undone.
          </p>
        </div>
        
        <div className="flex justify-end gap-2 mt-4">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? 'Removing...' : 'Remove Diagnostic'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

