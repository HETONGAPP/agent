/**
 * Custom Node Component for React Flow
 * Draggable card nodes with connection handles
 */

import { Handle, Position, NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { Device, Alarm, Diagnostic } from '@/types';
import { formatRelativeTime } from '@/utils/date';

interface NodeData {
  type: 'device' | 'alarm' | 'diagnostic';
  data: Device | Alarm | Diagnostic;
  label: string;
  description?: string;
}

export const CustomNode = ({ data, selected }: NodeProps<NodeData>) => {
  const { type, data: nodeData, label, description } = data;

  const getNodeStyles = () => {
    const baseStyles = 'rounded-lg shadow-lg p-4 min-w-[200px] transition-all duration-200 bg-gray-800';
    const selectedStyles = selected ? 'ring-2 ring-blue-500 ring-offset-2' : '';
    
    switch (type) {
      case 'device':
        const device = nodeData as Device;
        if (device.status === 'active') {
          return `${baseStyles} border-2 border-active ${selectedStyles}`;
        }
        if (device.status === 'inactive') {
          return `${baseStyles} border-2 border-inactive ${selectedStyles}`;
        }
        return `${baseStyles} border-2 border-gray-600 ${selectedStyles}`;
      
      case 'alarm':
        const alarm = nodeData as Alarm;
        if (alarm.severity === 'Critical') {
          return `${baseStyles} border-2 border-critical ${selectedStyles}`;
        }
        if (alarm.severity === 'Warning') {
          return `${baseStyles} border-2 border-warning ${selectedStyles}`;
        }
        if (alarm.severity === 'Info') {
          return `${baseStyles} border-2 border-info ${selectedStyles}`;
        }
        return `${baseStyles} border-2 border-gray-600 ${selectedStyles}`;
      
      case 'diagnostic':
        const diagnostic = nodeData as Diagnostic;
        if (diagnostic.risk_level === 'High') {
          return `${baseStyles} border-2 border-risk-high ${selectedStyles}`;
        }
        if (diagnostic.risk_level === 'Medium') {
          return `${baseStyles} border-2 border-risk-medium ${selectedStyles}`;
        }
        if (diagnostic.risk_level === 'Low') {
          return `${baseStyles} border-2 border-risk-low ${selectedStyles}`;
        }
        return `${baseStyles} border-2 border-gray-600 ${selectedStyles}`;
      
      default:
        return `${baseStyles} border-2 border-gray-600 ${selectedStyles}`;
    }
  };

  const renderNodeContent = () => {
    switch (type) {
      case 'device':
        const device = nodeData as Device;
        return (
          <>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">
                {device.device_type === 'BMS' && '🔋'}
                {device.device_type === 'PCS' && '⚡'}
                {device.device_type === 'EMS' && '📊'}
                {device.device_type === 'LOG' && '📝'}
              </span>
              <div>
                <div className="font-bold text-white">{label}</div>
                <div className="text-xs text-gray-400">{device.device_type}</div>
              </div>
            </div>
            <div className="text-sm text-gray-300">
              <div>Status: <span className="font-semibold">{device.status}</span></div>
              {device.last_seen && (
                <div className="text-xs text-gray-400 mt-1">
                  Last seen: {formatRelativeTime(device.last_seen)}
                </div>
              )}
            </div>
          </>
        );
      
      case 'alarm':
        const alarm = nodeData as Alarm;
        return (
          <>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">🚨</span>
              <div>
                <div className="font-bold text-white">{label}</div>
                <div className="text-xs text-gray-400">{alarm.alarm_type}</div>
              </div>
            </div>
            <div className="text-sm text-gray-300">
              <div>Severity: <span className="font-semibold">{alarm.severity}</span></div>
              <div className="text-xs text-gray-400 mt-1">
                {formatRelativeTime(alarm.timestamp)}
              </div>
            </div>
          </>
        );
      
      case 'diagnostic':
        const diagnostic = nodeData as Diagnostic;
        return (
          <>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">📋</span>
              <div>
                <div className="font-bold text-white">{label}</div>
                <div className="text-xs text-gray-400">Diagnostic Report</div>
              </div>
            </div>
            <div className="text-sm text-gray-300">
              <div>Risk: <span className="font-semibold">{diagnostic.risk_level}</span></div>
              {diagnostic.current_status && (
                <div className="text-xs text-gray-400 mt-1 truncate">
                  {diagnostic.current_status}
                </div>
              )}
            </div>
          </>
        );
      
      default:
        return <div className="font-bold text-white">{label}</div>;
    }
  };

  return (
    <motion.div
      className={getNodeStyles()}
      whileHover={{ scale: 1.05 }}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-blue-500" />
      {renderNodeContent()}
      {description && (
        <div className="text-xs text-gray-400 mt-2">{description}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-green-500" />
    </motion.div>
  );
};

