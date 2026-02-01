/**
 * Main Layout Component
 * Provides the overall page structure with navigation
 */

import { ReactNode } from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { PageTransition } from '@/components/ui/PageTransition';
import { useSidebarStore } from '@/store/useSidebarStore';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="h-screen bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 flex flex-col overflow-hidden">
      <Navbar />
      <div className="flex flex-1 overflow-hidden relative min-h-0">
        {/* Hide sidebar on mobile, show on desktop — h-full so sidebar fits and bottom release is visible */}
        <div className="hidden lg:flex lg:flex-col lg:h-full">
          <Sidebar />
        </div>
        <main 
          className="flex-1 w-full transition-all duration-300 overflow-y-auto bg-gradient-to-b from-transparent to-gray-900/50 scrollbar-thin"
          style={{ 
            marginLeft: 0,
            width: '100%',
            maxWidth: '100%',
            minWidth: 0,
            minHeight: 0,
            overflowX: 'hidden',
            padding: '0.75rem',
            paddingBottom: 'calc(6rem + env(safe-area-inset-bottom, 0px))'
          }}
        >
          <div style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box', paddingBottom: '4rem' }}>
            <PageTransition>
              {children}
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
};

