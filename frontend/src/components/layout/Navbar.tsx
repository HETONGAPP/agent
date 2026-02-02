/**
 * Navigation Bar Component
 * Mobile: header does not subscribe to menu state; dropdown is a separate component + Portal to avoid header re-render flicker when opening.
 */

import { useRef, useEffect, useCallback, memo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/store/useAuthStore';
import { useToastStore } from '@/store/useToastStore';
import { useMobileNavStore } from '@/store/useMobileNavStore';
import { useUserMenuStore } from '@/store/useUserMenuStore';
import { LogOut, User, Menu, LayoutDashboard, Map, Plug, Bell, FileText, Workflow } from 'lucide-react';
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

/** Mobile dropdown: standalone component; only this subscribes to open so header does not re-render */
function MobileNavPortal() {
  const open = useMobileNavStore((s) => s.open);
  const setOpen = useMobileNavStore((s) => s.setOpen);
  const location = useLocation();
  const justOpenedRef = useRef(false);
  const prevPathnameRef = useRef(location.pathname);

  useEffect(() => {
    if (open) {
      justOpenedRef.current = true;
      const t = setTimeout(() => { justOpenedRef.current = false; }, 380);
      return () => clearTimeout(t);
    }
  }, [open]);

  // Close menu only when route actually changes, to avoid closing immediately when open becomes true
  useEffect(() => {
    if (prevPathnameRef.current !== location.pathname) {
      prevPathnameRef.current = location.pathname;
      if (open) setOpen(false);
    }
  }, [location.pathname, open, setOpen]);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      const el = e.target as Element;
      if (justOpenedRef.current) return;
      if (el.closest?.('[data-mobile-nav-trigger]')) return;
      if (el.closest?.('[data-mobile-nav-portal]')) {
        if (el.closest?.('[data-mobile-nav-overlay]')) return;
        return;
      }
      setOpen(false);
    };
    document.addEventListener('click', handle, true);
    return () => document.removeEventListener('click', handle, true);
  }, [open, setOpen]);

  if (typeof document === 'undefined' || !document.body) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          data-mobile-nav-portal
          className="contents"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          <div
            data-mobile-nav-overlay
            className="fixed inset-0 bg-black/40 z-[90] lg:hidden"
            style={{ pointerEvents: 'auto', top: 'var(--header-height)' }}
            onClick={() => setOpen(false)}
          />
          <div
            className="fixed left-0 right-0 z-[100] lg:hidden rounded-b-xl bg-gray-800/80 backdrop-blur-md shadow-2xl border border-gray-600/80 overflow-hidden"
            style={{
              top: 'var(--header-height)',
              paddingLeft: 'calc(0.75rem + var(--safe-area-inset-left))',
              paddingRight: 'calc(0.75rem + var(--safe-area-inset-right))',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <nav className="py-4 px-2">
              <ul className="space-y-0.5">
                {mobileNavItems.map((item) => {
                  const isActive = location.pathname === item.path;
                  return (
                    <li key={item.path}>
                      <Link
                        to={item.path}
                        onClick={() => setOpen(false)}
                        className={`flex items-center gap-3 px-4 py-3 rounded-lg text-gray-300 transition-colors duration-150 ${
                          isActive
                            ? 'bg-blue-600/20 text-blue-400'
                            : 'hover:bg-gray-700/50 hover:text-white active:bg-gray-700/70'
                        }`}
                        style={{ WebkitTapHighlightColor: 'transparent', touchAction: 'manipulation' }}
                      >
                        <item.icon size={20} className="flex-shrink-0 text-current" />
                        <span className="text-sm font-medium">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
            <div className="py-3 text-center border-t border-gray-700/50">
              <span className="text-xs italic bg-gradient-to-r from-gray-400 via-gray-300 to-gray-500 bg-clip-text text-transparent font-medium">
                Version {RELEASE}
              </span>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

/** User menu dropdown: Portal; only this subscribes to open so header does not re-render on toggle (avoids mobile flash). */
function UserMenuPortal() {
  const open = useUserMenuStore((s) => s.open);
  const setOpen = useUserMenuStore((s) => s.setOpen);
  const { user, logout, isLoading } = useAuthStore();
  const { addToast } = useToastStore();
  const navigate = useNavigate();
  const justOpenedRef = useRef(false);

  useEffect(() => {
    if (open) {
      justOpenedRef.current = true;
      const t = setTimeout(() => { justOpenedRef.current = false; }, 300);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (justOpenedRef.current) return;
      const el = e.target as Element;
      if (el.closest?.('[data-user-menu-trigger]')) return;
      const inPortal = el.closest?.('[data-user-menu-portal]');
      const onOverlay = el.closest?.('[data-user-menu-overlay]');
      if (inPortal && onOverlay) return;
      if (inPortal) return;
      setOpen(false);
    };
    document.addEventListener('click', handle, true);
    return () => document.removeEventListener('click', handle, true);
  }, [open, setOpen]);

  const handleLogout = useCallback(async () => {
    setOpen(false);
    try {
      await logout();
      addToast('Logged out successfully', 'success');
      setTimeout(() => navigate('/login'), 100);
    } catch {
      addToast('Logged out', 'success');
      setTimeout(() => navigate('/login'), 100);
    }
  }, [logout, addToast, navigate, setOpen]);

  if (typeof document === 'undefined' || !document.body || !user) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          data-user-menu-portal
          className="contents"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
        >
          <div
            data-user-menu-overlay
            className="fixed inset-0 bg-black/30 z-[95]"
            style={{ top: 'var(--header-height)' }}
            onClick={() => setOpen(false)}
          />
          <div
            className="fixed right-2 sm:right-4 mt-2 w-48 sm:w-56 bg-gray-800/95 rounded-xl shadow-2xl border border-gray-700/50 py-2 z-[99]"
            style={{ top: 'calc(var(--header-height) + var(--safe-area-inset-top) + 0.5rem)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/50 to-transparent">
              <p className="text-sm font-medium text-white">{user.full_name || user.username}</p>
              <p className="text-xs text-gray-400 mt-1">{user.email}</p>
            </div>
            <div className="px-2 pb-2">
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); if (!isLoading) handleLogout(); }}
                disabled={isLoading}
                className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 active:bg-red-500/20 transition-colors disabled:opacity-50 rounded-lg"
              >
                <LogOut className="w-4 h-4" />
                {isLoading ? 'Logging out...' : 'Logout'}
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

/** Header content: does not subscribe to open or location to avoid re-render flicker when toggling menu or navigating */
const NavHeader = memo(function NavHeader() {
  const { user } = useAuthStore();

  return (
    <nav
      className="bg-gradient-to-r from-gray-800 via-gray-800 to-gray-900 border-b border-gray-700/50 px-3 sm:px-4 lg:px-6 py-2.5 sm:py-3 lg:py-4 shadow-lg relative z-[100] shrink-0 box-border"
      style={{
        height: 'var(--header-height)',
        minHeight: 'var(--header-height)',
        paddingTop: 'calc(0.625rem + var(--safe-area-inset-top))',
        paddingLeft: 'calc(0.75rem + var(--safe-area-inset-left))',
        paddingRight: 'calc(0.75rem + var(--safe-area-inset-right))',
        isolation: 'isolate',
        transform: 'translateZ(0)',
        contain: 'layout style',
      }}
    >
      <div className="flex items-center justify-between h-full min-h-0">
        <div className="flex items-center gap-2 sm:gap-3">
          <Link to="/" className="flex items-center gap-2 sm:gap-3 hover:opacity-90 transition-all duration-300 group ml-2 sm:ml-0">
            <img src={logoIcon} alt="BESS Agent Logo" className="h-8 sm:h-10 w-auto" />
            <span className="sm:hidden font-semibold text-white text-sm whitespace-nowrap">EasyGrid</span>
            <div className="flex flex-col hidden sm:flex">
              <h1 className="text-sm sm:text-base font-semibold text-white leading-tight bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                Easy Grid | BESS Diagnostic Agent
              </h1>
              <p className="text-xs text-gray-400 leading-tight hidden md:block">Energy Storage System</p>
            </div>
          </Link>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          <div className="lg:hidden flex items-center gap-1">
            <button
              type="button"
              data-mobile-nav-trigger
              onClick={() => useMobileNavStore.getState().setOpen((o) => !o)}
              className="flex items-center justify-center rounded-lg text-gray-300 hover:bg-gray-700/80 active:bg-gray-600/80 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              style={{
                WebkitTapHighlightColor: 'transparent',
                touchAction: 'manipulation',
                minWidth: 44,
                minHeight: 44,
              }}
              aria-label="Toggle navigation menu"
            >
              <Menu className="w-5 h-5 pointer-events-none" />
            </button>
          </div>
          <span className="font-mono text-xs text-gray-400 select-none hidden sm:inline" style={{ letterSpacing: '0.1em' }} title={`Release ${RELEASE}`}>
            v{RELEASE}
          </span>
          {user && (
            <button
              type="button"
              data-user-menu-trigger
              onClick={() => useUserMenuStore.getState().setOpen((o) => !o)}
              className="flex items-center justify-center gap-1 sm:gap-2 rounded-lg sm:rounded-xl text-gray-300 bg-transparent hover:bg-gray-700/80 active:bg-gray-600/80 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              style={{
                WebkitTapHighlightColor: 'transparent',
                touchAction: 'manipulation',
                minWidth: 44,
                minHeight: 44,
              }}
              aria-label="User menu"
            >
              <User className="w-5 h-5 flex-shrink-0 pointer-events-none" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </nav>
  );
});

export const Navbar = () => (
  <>
    <NavHeader />
    <MobileNavPortal />
    <UserMenuPortal />
  </>
);
