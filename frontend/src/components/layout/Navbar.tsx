/**
 * Navigation Bar Component
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/store/useAuthStore';
import { useToastStore } from '@/store/useToastStore';
import { LogOut, User, ChevronDown } from 'lucide-react';
import logoIcon from '@/assets/web.svg';

export const Navbar = () => {
  const navigate = useNavigate();
  const { user, logout, isLoading } = useAuthStore();
  const { addToast } = useToastStore();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };

    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showUserMenu]);

  const handleLogout = async () => {
    try {
      await logout();
      addToast('Logged out successfully', 'success');
      navigate('/login');
    } catch (error) {
      addToast('Logout failed', 'error');
    }
  };

  return (
    <motion.nav
      className="bg-gradient-to-r from-gray-800 via-gray-800 to-gray-900 border-b border-gray-700/50 px-6 py-4 shadow-lg backdrop-blur-sm"
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-all duration-300 group">
          <motion.img
            src={logoIcon}
            alt="BESS Agent Logo"
            className="h-10 w-auto"
            whileHover={{ scale: 1.1, rotate: 5 }}
            transition={{ type: "spring", stiffness: 400, damping: 10 }}
          />
          <div className="flex flex-col">
            <h1 className="text-base font-semibold text-white leading-tight bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
              Easy Grid | BESS Diagnostic Agent
            </h1>
            <p className="text-xs text-gray-400 leading-tight">Energy Storage System</p>
          </div>
        </Link>
        <div className="flex items-center gap-4">
          {user && (
            <div className="relative" ref={menuRef}>
              <motion.button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-gray-700 to-gray-600 hover:from-gray-600 hover:to-gray-500 rounded-xl text-white transition-all duration-300 shadow-md hover:shadow-lg"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {user.full_name || user.username}
                </span>
                <motion.div
                  animate={{ rotate: showUserMenu ? 180 : 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChevronDown className="w-4 h-4" />
                </motion.div>
              </motion.button>

              <AnimatePresence>
                {showUserMenu && (
                  <motion.div
                    className="absolute right-0 mt-2 w-56 bg-gray-800/95 backdrop-blur-md rounded-xl shadow-2xl border border-gray-700/50 py-2 z-50 overflow-hidden"
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="px-4 py-3 border-b border-gray-700/50 bg-gradient-to-r from-gray-800/50 to-transparent">
                      <p className="text-sm font-medium text-white">{user.full_name || user.username}</p>
                      <p className="text-xs text-gray-400 mt-1">{user.email}</p>
                    </div>
                    <motion.button
                      onClick={handleLogout}
                      disabled={isLoading}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      whileHover={{ x: 4 }}
                      transition={{ duration: 0.2 }}
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </motion.button>
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














