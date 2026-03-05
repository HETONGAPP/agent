/**
 * Sidebar Navigation Component
 * Collapsible sidebar with icon-only mode
 */

import { Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, LayoutDashboard, Map, Plug, Bell, FileText, Settings, X } from 'lucide-react';
import { useSidebarStore } from '@/store/useSidebarStore';

const navigationItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/datacenter', label: 'Data Center', icon: Map },
  { path: '/devices', label: 'Devices', icon: Plug },
  { path: '/alarms', label: 'Alarms', icon: Bell },
  { path: '/diagnostics', label: 'Diagnostics', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const Sidebar = () => {
  const location = useLocation();
  const { isCollapsed, isMobileOpen, toggle, closeMobile } = useSidebarStore();
  // Initialize isMobile based on window width, default to false for SSR
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 1024;
    }
    return false;
  });

  // Detect mobile screen size and ensure sidebar is closed on mobile initially
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      
      // On mobile, ensure sidebar is closed
      if (mobile && isMobileOpen) {
        console.log('[Sidebar] Mobile detected with open sidebar, closing');
        closeMobile();
      }
    };
    
    // Check immediately on mount
    checkMobile();
    
    // Also check on resize
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []); // Only run on mount
  
  // Separate effect to close sidebar when mobile is detected
  useEffect(() => {
    if (isMobile && isMobileOpen) {
      console.log('[Sidebar] Mobile mode active, closing sidebar');
      closeMobile();
    }
  }, [isMobile, isMobileOpen, closeMobile]);

  // Close mobile sidebar when route changes
  useEffect(() => {
    if (isMobileOpen) {
      console.log('[Sidebar] Route changed, closing mobile menu');
      closeMobile();
    }
  }, [location.pathname, isMobileOpen, closeMobile]);

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isMobileOpen && (
          <motion.div
            className="fixed inset-0 bg-black/50 z-[50] lg:hidden"
            style={{ pointerEvents: 'auto' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              console.log('[Sidebar] Overlay clicked, closing menu');
              closeMobile();
            }}
          />
        )}
      </AnimatePresence>

      <motion.aside
        className={`relative flex flex-col bg-gradient-to-b from-gray-800 to-gray-900 border-r border-gray-700/50 min-h-screen shadow-xl ${
          isCollapsed ? 'w-16' : 'w-64'
        } fixed lg:relative z-[60] lg:z-auto lg:min-h-0 lg:h-full`}
        style={{ 
          willChange: 'width, transform',
          top: 0,
          left: 0,
          height: isMobile ? '100vh' : '100%',
          minHeight: isMobile ? undefined : '100%',
          pointerEvents: isMobile && !isMobileOpen ? 'none' : 'auto',
          touchAction: 'pan-y'
        }}
        initial={{ 
          x: typeof window !== 'undefined' && window.innerWidth < 1024 ? -256 : 0,
          width: isCollapsed ? 64 : 256
        }}
        animate={{ 
          width: isMobile ? (isCollapsed ? 64 : 256) : (isCollapsed ? 64 : 256),
          x: isMobile && !isMobileOpen ? -256 : 0
        }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      >
      {/* Mobile close button */}
      <div className="lg:hidden flex items-center justify-between p-4 border-b border-gray-700/50" style={{ pointerEvents: 'auto', zIndex: 1 }}>
        <h2 className="text-white font-semibold">Menu</h2>
        <button
          onClick={(e) => {
            console.log('[Sidebar] Close button clicked');
            e.preventDefault();
            e.stopPropagation();
            closeMobile();
          }}
          onTouchEnd={(e) => {
            console.log('[Sidebar] Close button touch end');
            e.preventDefault();
            e.stopPropagation();
            closeMobile();
          }}
          className="p-2.5 rounded-lg text-gray-300 hover:bg-gray-700 active:bg-gray-600 transition-colors"
          aria-label="Close menu"
          type="button"
          style={{ 
            pointerEvents: 'auto',
            WebkitTapHighlightColor: 'transparent',
            touchAction: 'manipulation',
            minWidth: '44px',
            minHeight: '44px'
          }}
        >
          <X className="w-5 h-5 pointer-events-none" />
        </button>
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

      <nav className="flex-1 p-4 overflow-y-auto" style={{ pointerEvents: 'auto', zIndex: 1 }}>
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
                  onClick={(e) => {
                    console.log('[Sidebar] Navigation link clicked:', item.path);
                    // Close mobile menu when clicking a link
                    if (isMobileOpen) {
                      console.log('[Sidebar] Closing mobile menu after link click');
                      closeMobile();
                    }
                  }}
                  onTouchEnd={(e) => {
                    console.log('[Sidebar] Navigation link touch end:', item.path);
                    // Also close menu on touch
                    if (isMobileOpen) {
                      setTimeout(() => closeMobile(), 100);
                    }
                  }}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 group relative ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/30'
                      : 'text-gray-300 hover:bg-gray-700/50 hover:text-white active:bg-gray-700'
                  } ${isCollapsed ? 'justify-center px-2' : ''}`}
                  title={isCollapsed ? item.label : undefined}
                  style={{ 
                    pointerEvents: 'auto', 
                    zIndex: 1,
                    WebkitTapHighlightColor: 'transparent',
                    touchAction: 'manipulation',
                    minHeight: '44px' // Ensure touch target is large enough
                  }}
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

