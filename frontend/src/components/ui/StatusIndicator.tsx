/**
 * Status Indicator Component
 * Displays device status with colored indicator light
 */

interface StatusIndicatorProps {
  status: 'active' | 'inactive' | 'registered' | 'unknown' | string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const STATUS_COLORS = {
  active: 'bg-green-500',
  inactive: 'bg-red-500',
  registered: 'bg-blue-500',
  unknown: 'bg-gray-500',
  error: 'bg-yellow-500',
  warning: 'bg-yellow-500',
  critical: 'bg-red-500',
};

const STATUS_LABELS = {
  active: 'Active',
  inactive: 'Inactive',
  registered: 'Registered',
  unknown: 'Unknown',
  error: 'Error',
  warning: 'Warning',
  critical: 'Critical',
};

const SIZE_CLASSES = {
  sm: 'h-2 w-2',
  md: 'h-3 w-3',
  lg: 'h-4 w-4',
};

export const StatusIndicator = ({
  status,
  size = 'md',
  showLabel = false,
  className = '',
}: StatusIndicatorProps) => {
  const normalizedStatus = status?.toLowerCase() || 'unknown';
  const colorClass = STATUS_COLORS[normalizedStatus as keyof typeof STATUS_COLORS] || STATUS_COLORS.unknown;
  const label = STATUS_LABELS[normalizedStatus as keyof typeof STATUS_LABELS] || normalizedStatus;
  const sizeClass = SIZE_CLASSES[size];

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span
        className={`${sizeClass} ${colorClass} rounded-full inline-block ${
          normalizedStatus === 'active' ? 'animate-pulse' : ''
        }`}
        title={label}
      />
      {showLabel && (
        <span className="text-sm text-gray-300 capitalize">{label}</span>
      )}
    </div>
  );
};








