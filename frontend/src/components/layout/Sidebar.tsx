/**
 * Sidebar Navigation Component
 * Collapsible sidebar with icon-only mode
 */

import { Link, useLocation } from 'react-router-dom';
import { ChevronLeft, ChevronRight, LayoutDashboard, Map, Plug, Bell, FileText, Workflow } from 'lucide-react';
import { useSidebarStore } from '@/store/useSidebarStore';

const navigationItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/datacenter', label: 'Data Center', icon: Map },
  { path: '/devices', label: 'Devices', icon: Plug },
  { path: '/alarms', label: 'Alarms', icon: Bell },
  { path: '/diagnostics', label: 'Diagnostics', icon: FileText },
  { path: '/flow', label: 'Data Flow', icon: Workflow },
];

export const Sidebar = () => {
  const location = useLocation();
  const { isCollapsed, toggle } = useSidebarStore();

  return (
    <aside
      className={`bg-gray-800 border-r border-gray-700 min-h-screen relative transition-all duration-300 ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Toggle Button */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-20 z-10 w-6 h-6 bg-gray-700 hover:bg-gray-600 border border-gray-600 rounded-full flex items-center justify-center transition-colors shadow-lg"
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {isCollapsed ? (
          <ChevronRight size={14} className="text-gray-300" />
        ) : (
          <ChevronLeft size={14} className="text-gray-300" />
        )}
      </button>

      <nav className="p-4">
        <ul className="space-y-2">
          {navigationItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-all duration-200 group relative ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  } ${isCollapsed ? 'justify-center px-2' : ''}`}
                  title={isCollapsed ? item.label : undefined}
                >
                  <item.icon size={20} className="flex-shrink-0" />
                  {!isCollapsed && (
                    <span className="whitespace-nowrap overflow-hidden font-medium">
                      {item.label}
                    </span>
                  )}
                  
                  {/* Tooltip for collapsed state */}
                  {isCollapsed && (
                    <div className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-sm rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap transition-opacity z-50 shadow-lg">
                      {item.label}
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 w-2 h-2 bg-gray-900 rotate-45"></div>
                    </div>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
};

