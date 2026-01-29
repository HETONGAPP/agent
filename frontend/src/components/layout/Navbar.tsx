/**
 * Navigation Bar Component
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
    <nav className="bg-gray-800 border-b border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity group">
          <img 
            src={logoIcon} 
            alt="BESS Agent Logo" 
            className="h-10 w-auto transition-transform group-hover:scale-105" 
          />
          <div className="flex flex-col">
            <h1 className="text-base font-semibold text-white leading-tight">
              Easy Grid | BESS Diagnostic Agent
            </h1>
            <p className="text-xs text-gray-400 leading-tight">Energy Storage System</p>
          </div>
        </Link>
        <div className="flex items-center gap-4">
          {user && (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
              >
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">
                  {user.full_name || user.username}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
              </button>

              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-56 bg-gray-700 rounded-lg shadow-xl border border-gray-600 py-2 z-50">
                  <div className="px-4 py-3 border-b border-gray-600">
                    <p className="text-sm font-medium text-white">{user.full_name || user.username}</p>
                    <p className="text-xs text-gray-400 mt-1">{user.email}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    disabled={isLoading}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-300 hover:bg-gray-600 transition-colors disabled:opacity-50"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};














