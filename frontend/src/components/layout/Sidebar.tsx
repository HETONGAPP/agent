/**
 * Sidebar Navigation Component
 * Collapsible sidebar with icon-only mode
 */

import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, LayoutDashboard, Map, Plug, Bell, FileText, Workflow, X } from 'lucide-react';
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
  const { isCollapsed, isMobileOpen, toggle, closeMobile } = useSidebarStore();
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close mobile sidebar when route changes
  useEffect(() => {
    if (isMobileOpen) {
      closeMobile();
    }
  }, [location.pathname, isMobileOpen, closeMobile]);

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isMobileOpen && (
          <motion.div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeMobile}
          />
        )}
      </AnimatePresence>

      <motion.aside
        className={`bg-gradient-to-b from-gray-800 to-gray-900 border-r border-gray-700/50 min-h-screen relative shadow-xl ${
          isCollapsed ? 'w-16' : 'w-64'
        } fixed lg:relative z-50 lg:z-auto`}
        style={{ willChange: 'width, transform' }}
        initial={false}
        animate={{ 
          width: isCollapsed ? 64 : 256,
          x: isMobile && !isMobileOpen ? -256 : 0
        }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      >
      {/* Mobile close button */}
      <div className="lg:hidden flex items-center justify-between p-4 border-b border-gray-700/50">
        <h2 className="text-white font-semibold">Menu</h2>
        <motion.button
          onClick={closeMobile}
          className="p-2 rounded-lg text-gray-300 hover:bg-gray-700 transition-colors"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </motion.button>
      </div>

      {/* Desktop Toggle Button */}
      <motion.button
        onClick={toggle}
        className="hidden lg:flex absolute -right-3 top-20 z-10 w-6 h-6 bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 border border-gray-600 rounded-full items-center justify-center shadow-lg"
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <motion.div
          animate={{ rotate: isCollapsed ? 0 : 180 }}
          transition={{ duration: 0.3 }}
        >
          <ChevronRight size={14} className="text-gray-300" />
        </motion.div>
      </motion.button>

      <nav className="p-4">
        <ul className="space-y-2">
          {navigationItems.map((item, index) => {
            const isActive = location.pathname === item.path;
            return (
              <motion.li
                key={item.path}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.03, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              >
                <Link
                  to={item.path}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group relative ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/30'
                      : 'text-gray-300 hover:bg-gray-700/50 hover:text-white'
                  } ${isCollapsed ? 'justify-center px-2' : ''}`}
                  title={isCollapsed ? item.label : undefined}
                >
                  {isActive && (
                    <motion.div
                      className="absolute left-0 top-0 bottom-0 w-1 bg-white rounded-r-full"
                      style={{ willChange: 'transform' }}
                      layoutId="activeIndicator"
                      transition={{ type: "spring", stiffness: 400, damping: 35, mass: 0.5 }}
                    />
                  )}
                  <motion.div
                    style={{ willChange: 'transform' }}
                    whileHover={{ scale: 1.1 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <item.icon size={20} className="flex-shrink-0" />
                  </motion.div>
                  <AnimatePresence>
                    {!isCollapsed && (
                      <motion.span
                        className="whitespace-nowrap overflow-hidden font-medium"
                        style={{ willChange: 'opacity' }}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  
                  {/* Enhanced Tooltip for collapsed state */}
                  {isCollapsed && (
                    <motion.div
                      className="absolute left-full ml-2 px-3 py-2 bg-gray-900/95 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-xl border border-gray-700"
                      style={{ willChange: 'opacity, transform' }}
                      initial={{ opacity: 0 }}
                      whileHover={{ opacity: 1 }}
                      transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                    >
                      {item.label}
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 w-2 h-2 bg-gray-900 rotate-45 border-l border-t border-gray-700"></div>
                    </motion.div>
                  )}
                </Link>
              </motion.li>
            );
          })}
        </ul>
      </nav>
      </motion.aside>
    </>
  );
};

