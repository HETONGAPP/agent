/**
 * Navigation Bar Component
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/store/useAuthStore';
import { useToastStore } from '@/store/useToastStore';
import { LogOut, User, ChevronDown, Menu, LayoutDashboard, Map, Plug, Bell, FileText, Workflow } from 'lucide-react';
import logoIcon from '@/assets/web.svg';
import { RELEASE } from '@/config/constants';

const mobileNavItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/datacenter', label: 'Data Center', icon: Map },
  { path: '/devices', label: 'Devices', icon: Plug },
  { path: '/alarms', label: 'Alarms', icon: Bell },
  { path: '/diagnostics', label: 'Diagnostics', icon: FileText },
  { path: '/flow', label: 'Data Flow', icon: Workflow },
];

export const Navbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isLoading } = useAuthStore();
  const { addToast } = useToastStore();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showMobileNav, setShowMobileNav] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const mobileNavRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      // Don't close if clicking on logout button or any button inside menu
      if (target instanceof Element) {
        const button = target.closest('button');
        if (button && menuRef.current?.contains(button)) {
          console.log('[Navbar] Clicked on button inside menu, not closing');
          return;
        }
        // Don't close if clicking on mobile nav items
        if (mobileNavRef.current?.contains(target)) {
          return;
        }
      }
      if (menuRef.current && !menuRef.current.contains(target)) {
        console.log('[Navbar] Clicked outside menu, closing');
        setShowUserMenu(false);
      }
      if (mobileNavRef.current && !mobileNavRef.current.contains(target)) {
        setShowMobileNav(false);
      }
    };

    if (showUserMenu || showMobileNav) {
      document.addEventListener('click', handleClickOutside, true);
      return () => {
        document.removeEventListener('click', handleClickOutside, true);
      };
    }
  }, [showUserMenu, showMobileNav]);
  
  // Close mobile nav when route changes
  useEffect(() => {
    if (showMobileNav) {
      setShowMobileNav(false);
    }
  }, [location.pathname]);

  const handleLogout = async () => {
    console.log('[Navbar] Logout button clicked');
    try {
      // Close menu first
      setShowUserMenu(false);
      console.log('[Navbar] Calling logout function...');
      // Call logout - this will clear cookie and local state
      await logout();
      console.log('[Navbar] Logout successful, navigating to login');
      addToast('Logged out successfully', 'success');
      // Small delay to ensure state is cleared before navigation
      setTimeout(() => {
        navigate('/login');
      }, 100);
    } catch (error) {
      console.error('[Navbar] Logout error:', error);
      // Even if logout fails, clear state and navigate
      addToast('Logged out', 'success');
      setTimeout(() => {
        navigate('/login');
      }, 100);
    }
  };

  return (
    <motion.nav
      className="bg-gradient-to-r from-gray-800 via-gray-800 to-gray-900 border-b border-gray-700/50 px-3 sm:px-4 lg:px-6 py-2 sm:py-3 lg:py-4 shadow-lg relative z-[100]"
      style={{ 
        willChange: 'transform, opacity',
        position: 'relative'
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mobile navigation dropdown button */}
          <div className="lg:hidden relative" ref={mobileNavRef}>
            <button
              onClick={() => {
                console.log('[Navbar] Mobile nav button clicked');
                setShowMobileNav(!showMobileNav);
              }}
              className="p-2.5 rounded-lg text-gray-300 hover:bg-gray-700 active:bg-gray-600 transition-colors relative"
              style={{ 
                zIndex: 200, 
                position: 'relative', 
                pointerEvents: 'auto',
                WebkitTapHighlightColor: 'transparent',
                touchAction: 'manipulation',
                minWidth: '44px',
                minHeight: '44px',
                cursor: 'pointer'
              }}
              aria-label="Toggle navigation menu"
              type="button"
            >
              <Menu className="w-5 h-5 pointer-events-none" />
            </button>
            
            {/* Mobile Navigation Dropdown */}
            <AnimatePresence>
              {showMobileNav && (
                <>
                  {/* Overlay */}
                  <motion.div
                    className="fixed inset-0 bg-black/50 z-[90] lg:hidden"
                    style={{ pointerEvents: 'auto' }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => {
                      console.log('[Navbar] Mobile nav overlay clicked, closing');
                      setShowMobileNav(false);
                    }}
                  />
                  
                  {/* Dropdown Menu */}
                  <motion.div
                    className="fixed left-3 top-14 w-[calc(100%-1.5rem)] max-w-xs bg-gray-800/95 backdrop-blur-md rounded-xl shadow-2xl border border-gray-700/50 py-2 z-[100] lg:hidden"
                    style={{ 
                      willChange: 'transform, opacity',
                      zIndex: 100,
                      maxHeight: 'calc(100vh - 4rem)',
                      overflowY: 'auto'
                    }}
                    initial={{ opacity: 0, scale: 0.95, y: -10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -10 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <nav>
                      <ul className="space-y-1">
                        {mobileNavItems.map((item) => {
                          const isActive = location.pathname === item.path;
                          return (
                            <li key={item.path}>
                              <Link
                                to={item.path}
                                onClick={() => {
                                  console.log('[Navbar] Mobile nav link clicked:', item.path);
                                  setShowMobileNav(false);
                                }}
                                className={`flex items-center gap-3 px-4 py-3 mx-2 rounded-lg transition-all duration-200 ${
                                  isActive
                                    ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/30'
                                    : 'text-gray-300 hover:bg-gray-700/50 hover:text-white active:bg-gray-700'
                                }`}
                                style={{ 
                                  WebkitTapHighlightColor: 'transparent',
                                  touchAction: 'manipulation',
                                  minHeight: '44px',
                                  display: 'flex',
                                  alignItems: 'center'
                                }}
                              >
                                <item.icon size={20} className="flex-shrink-0" />
                                <span className="font-medium">{item.label}</span>
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </nav>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
          
          <Link to="/" className="flex items-center gap-2 sm:gap-3 hover:opacity-90 transition-all duration-300 group">
            <motion.img
              src={logoIcon}
              alt="BESS Agent Logo"
              className="h-8 sm:h-10 w-auto"
              style={{ willChange: 'transform' }}
              whileHover={{ scale: 1.05 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            />
            <div className="flex flex-col hidden sm:flex">
              <h1 className="text-sm sm:text-base font-semibold text-white leading-tight bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                Easy Grid | BESS Diagnostic Agent
              </h1>
              <p className="text-xs text-gray-400 leading-tight hidden md:block">Energy Storage System</p>
            </div>
          </Link>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          <span
            className="font-mono text-xs text-gray-400 select-none hidden sm:inline"
            style={{ letterSpacing: '0.1em' }}
            title={`Release ${RELEASE}`}
          >
            v{RELEASE}
          </span>
          {user && (
            <div className="relative" ref={menuRef} style={{ zIndex: 10000, position: 'relative' }}>
              <motion.button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-2 bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-lg sm:rounded-xl text-white transition-all duration-200 shadow-md hover:shadow-lg"
                style={{ willChange: 'transform' }}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                transition={{ duration: 0.15 }}
              >
                <User className="w-4 h-4 flex-shrink-0" />
                <span className="text-xs sm:text-sm font-medium hidden sm:inline">
                  {user.full_name || user.username}
                </span>
                <motion.div
                  animate={{ rotate: showUserMenu ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronDown className="w-4 h-4 hidden sm:block" />
                </motion.div>
              </motion.button>

              <AnimatePresence>
                {showUserMenu && (
                  <motion.div
                    className="fixed right-2 sm:right-4 mt-2 w-48 sm:w-56 bg-gray-800/95 rounded-xl shadow-2xl border border-gray-700/50 py-2"
                    style={{ 
                      willChange: 'transform, opacity',
                      zIndex: 99999,
                      top: '56px' // Adjust based on navbar height (mobile is smaller)
                    }}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                    onClick={(e) => {
                      // Only stop propagation if not clicking on button
                      if (!(e.target instanceof Element && e.target.closest('button'))) {
                        e.stopPropagation();
                      }
                    }}
                  >
                    <div className="px-4 py-3 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/50 to-transparent">
                      <p className="text-sm font-medium text-white">{user.full_name || user.username}</p>
                      <p className="text-xs text-gray-400 mt-1">{user.email}</p>
                    </div>
                    <div className="px-2 pb-2">
                      <button
                        onClick={(e) => {
                          console.log('[Navbar] Logout button clicked - event:', e);
                          e.preventDefault();
                          e.stopPropagation();
                          console.log('[Navbar] After preventDefault/stopPropagation');
                          if (!isLoading) {
                            console.log('[Navbar] Calling handleLogout');
                            handleLogout();
                          } else {
                            console.log('[Navbar] Logout already in progress');
                          }
                        }}
                        onMouseDown={(e) => {
                          console.log('[Navbar] Logout button onMouseDown');
                          e.stopPropagation();
                        }}
                        disabled={isLoading}
                        className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 active:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer rounded-lg"
                        type="button"
                      >
                        <LogOut className="w-4 h-4" />
                        {isLoading ? 'Logging out...' : 'Logout'}
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </motion.nav>
  );
};














