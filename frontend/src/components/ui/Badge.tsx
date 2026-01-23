/**
 * Badge Component
 * Color-coded badge for status, severity, risk levels
 */

import { AlarmSeverity, RiskLevel, DeviceStatus, ALARM_SEVERITY, RISK_LEVELS, DEVICE_STATUS } from '@/config/constants';

interface BadgeProps {
  type: 'severity' | 'risk' | 'status';
  value: AlarmSeverity | RiskLevel | DeviceStatus | string;
  size?: 'sm' | 'md' | 'lg';
}

export const Badge = ({ type, value, size = 'md' }: BadgeProps) => {
  const getColorClass = () => {
    switch (type) {
      case 'severity':
        if (value === ALARM_SEVERITY.CRITICAL) {
          return 'bg-critical/20 text-critical border-critical/50';
        }
        if (value === ALARM_SEVERITY.WARNING) {
          return 'bg-warning/20 text-warning border-warning/50';
        }
        if (value === ALARM_SEVERITY.INFO) {
          return 'bg-info/20 text-info border-info/50';
        }
        return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
      
      case 'risk':
        if (value === RISK_LEVELS.HIGH) {
          return 'bg-risk-high/20 text-risk-high border-risk-high/50';
        }
        if (value === RISK_LEVELS.MEDIUM) {
          return 'bg-risk-medium/20 text-risk-medium border-risk-medium/50';
        }
        if (value === RISK_LEVELS.LOW) {
          return 'bg-risk-low/20 text-risk-low border-risk-low/50';
        }
        return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
      
      case 'status':
        if (value === DEVICE_STATUS.ACTIVE) {
          return 'bg-active/20 text-active border-active/50';
        }
        if (value === DEVICE_STATUS.INACTIVE) {
          return 'bg-inactive/20 text-inactive border-inactive/50';
        }
        if (value === DEVICE_STATUS.REGISTERED) {
          return 'bg-info/20 text-info border-info/50';
        }
        return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
      
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
    }
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span
      className={`badge border ${getColorClass()} ${sizeClasses[size]}`}
    >
      {value}
    </span>
  );
};

