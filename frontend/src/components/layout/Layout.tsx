/**
 * Main Layout Component
 * Provides the overall page structure with navigation
 */

import { ReactNode } from 'react';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useSidebarStore } from '@/store/useSidebarStore';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const { isCollapsed } = useSidebarStore();

  return (
    <div className="h-screen bg-gray-900 flex flex-col overflow-hidden">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main 
          className="flex-1 p-6 transition-all duration-300 overflow-y-auto"
          style={{ marginLeft: 0 }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};

