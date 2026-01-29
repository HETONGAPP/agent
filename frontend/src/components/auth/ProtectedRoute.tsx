/**
 * Protected Route Component
 * Wraps routes that require authentication
 */

import { useEffect, useRef } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { useToastStore } from '@/store/useToastStore';
import { useSiteDiagnosticStore } from '@/store/useSiteDiagnosticStore';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, isLoading, token, fetchUserInfo } = useAuthStore();
  const { clearToasts } = useToastStore();
  const { clearToastHistory } = useSiteDiagnosticStore();
  const location = useLocation();
  const hasClearedToasts = useRef(false);

  useEffect(() => {
    // If we have a token but user info is not loaded, fetch it
    if (token && !isAuthenticated && !isLoading) {
      fetchUserInfo();
    }
  }, [token, isAuthenticated, isLoading, fetchUserInfo]);

  // Clear all notifications when user successfully authenticates
  useEffect(() => {
    if (isAuthenticated && !hasClearedToasts.current) {
      console.log('[ProtectedRoute] User authenticated, clearing all notifications');
      clearToasts();
      clearToastHistory();
      hasClearedToasts.current = true;
    }
    // Reset flag when user logs out
    if (!isAuthenticated) {
      hasClearedToasts.current = false;
    }
  }, [isAuthenticated, clearToasts, clearToastHistory]);

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Render protected content
  return <>{children}</>;
};
