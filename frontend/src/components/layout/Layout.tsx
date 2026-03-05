/**
 * Main Layout Component
 * Provides the overall page structure with navigation.
 * Mobile: uses 100dvh, safe-area insets, and responsive gutters (aligned with website approach).
 */

import { ReactNode, useEffect } from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { PageTransition } from '@/components/ui/PageTransition';
import { useMapThemeStore } from '@/store/useMapThemeStore';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const mapTheme = useMapThemeStore((s) => s.mapTheme);

  useEffect(() => {
    document.body.classList.remove('map-theme-dark', 'map-theme-light');
    document.body.classList.add(`map-theme-${mapTheme}`);
  }, [mapTheme]);

  return (
    <div
      className="flex flex-col overflow-hidden bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 min-h-screen"
      style={{
        minHeight: '100dvh',
        height: '100dvh',
      }}
    >
      <Navbar />
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
        <div className="hidden lg:flex lg:flex-col lg:min-h-full lg:self-stretch">
          <Sidebar />
        </div>
        <main
          className="flex-1 w-full min-w-0 min-h-0 overflow-x-hidden overflow-y-auto bg-gradient-to-b from-transparent to-gray-900/50 scrollbar-thin transition-all duration-300"
          style={{
            padding: 'var(--layout-main-padding)',
            paddingLeft: 'calc(var(--layout-main-padding) + var(--safe-area-inset-left))',
            paddingRight: 'calc(var(--layout-main-padding) + var(--safe-area-inset-right))',
            paddingBottom: 'calc(var(--main-padding-bottom) + var(--safe-area-inset-bottom))',
          }}
        >
          <div className="w-full max-w-full box-border">
            <PageTransition>
              {children}
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
};

