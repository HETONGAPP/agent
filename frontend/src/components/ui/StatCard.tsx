/**
 * Statistics Card Component
 * Reusable card for displaying statistics
 */

import React, { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon | ReactNode;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple';
  onClick?: () => void;
}

export const StatCard = ({
  title,
  value,
  icon,
  trend,
  color = 'blue',
  onClick,
}: StatCardProps) => {
  const colorClasses = {
    blue: 'border-blue-500/30 bg-gradient-to-br from-blue-500/10 via-blue-500/5 to-transparent',
    green: 'border-green-500/30 bg-gradient-to-br from-green-500/10 via-green-500/5 to-transparent',
    red: 'border-red-500/30 bg-gradient-to-br from-red-500/10 via-red-500/5 to-transparent',
    yellow: 'border-yellow-500/30 bg-gradient-to-br from-yellow-500/10 via-yellow-500/5 to-transparent',
    purple: 'border-purple-500/30 bg-gradient-to-br from-purple-500/10 via-purple-500/5 to-transparent',
  };

  const iconColorClasses = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  };

  const iconBgClasses = {
    blue: 'bg-blue-500/20',
    green: 'bg-green-500/20',
    red: 'bg-red-500/20',
    yellow: 'bg-yellow-500/20',
    purple: 'bg-purple-500/20',
  };

  // Render icon component
  const renderIcon = (): React.ReactElement | null => {
    if (!icon) return null;
    
    // Type guard: Check if it's a function component (LucideIcon)
    // This must be checked FIRST before any object checks
    if (typeof icon === 'function') {
      const IconComponent = icon as LucideIcon;
      return <IconComponent size={28} className="sm:w-8 sm:h-8" strokeWidth={1.5} />;
    }
    
    // Type guard: Check if it's a primitive value (safe to render)
    if (typeof icon === 'string' || typeof icon === 'number' || typeof icon === 'boolean') {
      return <div className="text-4xl">{String(icon)}</div>;
    }
    
    // Type guard: Check if it's a valid React element
    // Must be an object, have $$typeof, and pass React.isValidElement check
    // Also check that it's not a component object by ensuring it doesn't have a 'render' method
    // (class components have render, but elements don't)
    if (
      typeof icon === 'object' &&
      icon !== null &&
      '$$typeof' in icon &&
      !('render' in icon) && // Exclude class component objects
      React.isValidElement(icon)
    ) {
      return icon as React.ReactElement;
    }
    
    // Don't render anything else - this prevents "Objects are not valid as a React child"
    return null;
  };

  // Check if icon is a LucideIcon component for styling
  const isLucideIcon = icon && typeof icon === 'function';

  return (
    <motion.div
      className={`card card-hover border ${colorClasses[color]} ${onClick ? 'cursor-pointer' : ''} rounded-xl shadow-none sm:shadow-lg sm:hover:shadow-xl relative overflow-hidden`}
      style={{ willChange: 'transform, opacity' }}
      whileHover={{ scale: 1.02 }}
      onClick={onClick}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
    >
      {/* Decorative gradient overlay */}
      <div className={`absolute top-0 right-0 w-32 h-32 ${iconBgClasses[color]} rounded-full blur-3xl opacity-30 -z-0`} />
      
      <div className="flex items-center justify-between relative z-10">
        <div className="flex-1 min-w-0">
          <p className="text-xs sm:text-sm text-gray-400 mb-1 sm:mb-2 font-medium uppercase tracking-wide truncate">{title}</p>
          <p className="text-2xl sm:text-3xl font-bold text-white mb-1 bg-gradient-to-r from-white to-gray-200 bg-clip-text text-transparent truncate">
            {value}
          </p>
          {trend && (
            <motion.p
              className={`text-xs mt-2 font-semibold inline-flex items-center gap-1 ${
                trend.isPositive ? 'text-green-400' : 'text-red-400'
              }`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
            >
              <span>{trend.isPositive ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
            </motion.p>
          )}
        </div>
        {icon && (
          <motion.div
            className={`${isLucideIcon ? iconColorClasses[color] : 'opacity-60'} p-2 sm:p-3 rounded-lg sm:rounded-xl ${iconBgClasses[color]} flex-shrink-0`}
            style={{ willChange: 'transform' }}
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            {typeof icon === 'function' ? (
              <icon size={24} className="sm:w-8 sm:h-8" strokeWidth={1.5} />
            ) : (
              renderIcon()
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};


