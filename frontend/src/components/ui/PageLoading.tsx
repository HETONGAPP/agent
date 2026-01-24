/**
 * Page Loading Component
 * Full-page loading indicator for page-level loading states
 */

import { LoadingSpinner } from './LoadingSpinner';

interface PageLoadingProps {
  message?: string;
  className?: string;
}

export const PageLoading = ({ message = 'Loading...', className = '' }: PageLoadingProps) => {
  return (
    <div className={`flex flex-col items-center justify-center min-h-[60vh] ${className}`}>
      <LoadingSpinner size="lg" />
      <p className="mt-4 text-gray-400 text-sm">{message}</p>
    </div>
  );
};


