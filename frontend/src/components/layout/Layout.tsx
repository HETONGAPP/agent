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
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar />
        <main 
          className="flex-1 p-4 sm:p-6 transition-all duration-300 overflow-y-auto bg-gradient-to-b from-transparent to-gray-900/50 scrollbar-thin lg:ml-0"
        >
          <PageTransition>
            {children}
          </PageTransition>
        </main>
      </div>
    </div>
  );
};

