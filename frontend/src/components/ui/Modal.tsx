/**
 * Modal Component
 * Reusable modal dialog
 */

import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** When true, no entrance/exit animation (avoids flash on mobile) */
  noAnimation?: boolean;
}

// Lock body + layout main scroll when any modal is open (supports multiple modals)
const MODAL_OPEN_BODY_CLASS = 'modal-open';
let openModalCount = 0;

function useModalScrollLock(isOpen: boolean) {
  useEffect(() => {
    if (!isOpen) return;
    openModalCount += 1;
    document.body.classList.add(MODAL_OPEN_BODY_CLASS);
    document.body.style.overflow = 'hidden';
    const main = document.querySelector('main');
    if (main instanceof HTMLElement) {
      main.style.overflow = 'hidden';
      main.style.touchAction = 'none';
    }
    return () => {
      openModalCount = Math.max(0, openModalCount - 1);
      if (openModalCount === 0) {
        document.body.classList.remove(MODAL_OPEN_BODY_CLASS);
        document.body.style.overflow = 'unset';
        const el = document.querySelector('main');
        if (el instanceof HTMLElement) {
          el.style.overflow = '';
          el.style.touchAction = '';
        }
      }
    };
  }, [isOpen]);
}

export const Modal = ({ isOpen, onClose, title, children, size = 'md', noAnimation = false }: ModalProps) => {
  useModalScrollLock(isOpen);

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const sizeClasses = {
    sm: 'max-w-full sm:max-w-md',
    md: 'max-w-full sm:max-w-lg',
    lg: 'max-w-full sm:max-w-2xl',
    xl: 'max-w-full sm:max-w-4xl',
  };

  const backdropClass = 'fixed inset-0 bg-black/50 z-40';
  const panelClass = `bg-gray-800 rounded-lg shadow-2xl w-full min-w-0 ${sizeClasses[size]} max-h-[85dvh] sm:max-h-[90vh] overflow-hidden flex flex-col`;
  const wrapperStyle = {
    paddingLeft: 'max(0.5rem, env(safe-area-inset-left))',
    paddingRight: 'max(0.5rem, env(safe-area-inset-right))',
    paddingTop: 'max(0.5rem, env(safe-area-inset-top))',
    paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))',
  };

  if (noAnimation) {
    if (!isOpen) return null;
    return (
      <>
        <div className={backdropClass} onClick={onClose} aria-hidden />
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4"
          style={wrapperStyle}
        >
          <div className={panelClass}>
            {title && (
              <div className="flex items-center justify-between p-3 sm:p-4 border-b border-gray-700">
                <h2 className="text-lg sm:text-xl font-bold text-white truncate pr-2">{title}</h2>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-gray-700 flex-shrink-0"
                  aria-label="Close modal"
                >
                  <X size={20} />
                </button>
              </div>
            )}
            <div className={title ? 'p-3 sm:p-4 overflow-y-auto flex-1' : 'p-3 sm:p-4 overflow-y-auto flex-1'}>
              {children}
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className={backdropClass}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4" style={wrapperStyle}>
            <motion.div
              className={panelClass}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              {title && (
                <div className="flex items-center justify-between p-3 sm:p-4 border-b border-gray-700">
                  <h2 className="text-lg sm:text-xl font-bold text-white truncate pr-2">{title}</h2>
                  <button
                    onClick={onClose}
                    className="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-gray-700 flex-shrink-0"
                    aria-label="Close modal"
                  >
                    <X size={20} />
                  </button>
                </div>
              )}
              <div className={title ? 'p-3 sm:p-4 overflow-y-auto flex-1' : 'p-3 sm:p-4 overflow-y-auto flex-1'}>
                {children}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};







