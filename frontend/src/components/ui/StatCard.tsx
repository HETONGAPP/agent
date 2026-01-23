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
    blue: 'border-blue-500/50 bg-blue-500/10',
    green: 'border-green-500/50 bg-green-500/10',
    red: 'border-red-500/50 bg-red-500/10',
    yellow: 'border-yellow-500/50 bg-yellow-500/10',
    purple: 'border-purple-500/50 bg-purple-500/10',
  };

  const iconColorClasses = {
    blue: 'text-blue-400',
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  };

  // Render icon component
  const renderIcon = (): React.ReactElement | null => {
    if (!icon) return null;
    
    // Type guard: Check if it's a function component (LucideIcon)
    // This must be checked FIRST before any object checks
    if (typeof icon === 'function') {
      const IconComponent = icon as LucideIcon;
      return <IconComponent size={32} strokeWidth={1.5} />;
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
      className={`card card-hover border-2 ${colorClasses[color]} ${onClick ? 'cursor-pointer' : ''} backdrop-blur-sm`}
      whileHover={{ scale: 1.02, y: -2 }}
      onClick={onClick}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-400 mb-2 font-medium">{title}</p>
          <p className="text-3xl font-bold text-white mb-1">{value}</p>
          {trend && (
            <p
              className={`text-xs mt-2 font-medium ${
                trend.isPositive ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </p>
          )}
        </div>
        {icon && (
          <div className={isLucideIcon ? iconColorClasses[color] : 'opacity-60'}>
            {renderIcon()}
          </div>
        )}
      </div>
    </motion.div>
  );
};


