/**
 * Node Details Panel Component
 * Side panel for displaying node details
 */

import { X } from 'lucide-react';
import { Device, Alarm, Diagnostic } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { formatRelativeTime, formatAbsoluteTime } from '@/utils/date';
import { Button } from '@/components/ui/Button';

interface NodeDetailsPanelProps {
  node: {
    type: 'device' | 'alarm' | 'diagnostic';
    data: Device | Alarm | Diagnostic;
  } | null;
  onClose: () => void;
}

export const NodeDetailsPanel = ({ node, onClose }: NodeDetailsPanelProps) => {
  if (!node) return null;

  const renderDeviceDetails = (device: Device) => (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Device ID</h3>
        <p className="text-white font-mono">{device.device_id}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Device Type</h3>
        <Badge type="status" value={device.device_type} />
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Status</h3>
        <Badge type="status" value={device.status} />
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Integration</h3>
        <p className="text-white">{device.integration_name}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Registered At</h3>
        <p className="text-white text-sm">{formatAbsoluteTime(device.registered_at)}</p>
        <p className="text-gray-400 text-xs">{formatRelativeTime(device.registered_at)}</p>
      </div>
      {device.last_seen && (
        <div>
          <h3 className="text-sm text-gray-400 mb-1">Last Seen</h3>
          <p className="text-white text-sm">{formatAbsoluteTime(device.last_seen)}</p>
          <p className="text-gray-400 text-xs">{formatRelativeTime(device.last_seen)}</p>
        </div>
      )}
      {Object.keys(device.metadata).length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 mb-1">Metadata</h3>
          <pre className="text-xs text-gray-300 bg-gray-900 p-2 rounded overflow-auto">
            {JSON.stringify(device.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );

  const renderAlarmDetails = (alarm: Alarm) => (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Alarm ID</h3>
        <p className="text-white font-mono">{alarm.alarm_id}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Alarm Type</h3>
        <p className="text-white">{alarm.alarm_type}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Severity</h3>
        <Badge type="severity" value={alarm.severity} />
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Source</h3>
        <p className="text-white">{alarm.source}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Timestamp</h3>
        <p className="text-white text-sm">{formatAbsoluteTime(alarm.timestamp)}</p>
        <p className="text-gray-400 text-xs">{formatRelativeTime(alarm.timestamp)}</p>
      </div>
      {alarm.site_id && (
        <div>
          <h3 className="text-sm text-gray-400 mb-1">Site ID</h3>
          <p className="text-white">{alarm.site_id}</p>
        </div>
      )}
      {alarm.diagnostic && (
        <div>
          <h3 className="text-sm text-gray-400 mb-1">Diagnostic</h3>
          <Badge type="risk" value={alarm.diagnostic.risk_level} />
        </div>
      )}
    </div>
  );

  const renderDiagnosticDetails = (diagnostic: Diagnostic) => (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Alarm ID</h3>
        <p className="text-white font-mono">{diagnostic.alarm_id}</p>
      </div>
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Risk Level</h3>
        <Badge type="risk" value={diagnostic.risk_level} />
      </div>
      {diagnostic.current_status && (
        <div>
          <h3 className="text-sm text-gray-400 mb-1">Current Status</h3>
          <p className="text-white">{diagnostic.current_status}</p>
        </div>
      )}
      {diagnostic.possible_causes && diagnostic.possible_causes.length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 mb-2">Possible Causes</h3>
          <ul className="list-disc list-inside space-y-1">
            {diagnostic.possible_causes.map((cause, index) => (
              <li key={index} className="text-gray-300 text-sm">{cause}</li>
            ))}
          </ul>
        </div>
      )}
      {diagnostic.recommended_actions && diagnostic.recommended_actions.length > 0 && (
        <div>
          <h3 className="text-sm text-gray-400 mb-2">Recommended Actions</h3>
          <ul className="list-disc list-inside space-y-1">
            {diagnostic.recommended_actions.map((action, index) => (
              <li key={index} className="text-gray-300 text-sm">{action}</li>
            ))}
          </ul>
        </div>
      )}
      {diagnostic.markdown && (
        <div>
          <h3 className="text-sm text-gray-400 mb-2">Full Report</h3>
          <pre className="text-xs text-gray-300 bg-gray-900 p-3 rounded overflow-auto max-h-60">
            {diagnostic.markdown}
          </pre>
        </div>
      )}
      <div>
        <h3 className="text-sm text-gray-400 mb-1">Generated At</h3>
        <p className="text-white text-sm">{formatAbsoluteTime(diagnostic.timestamp)}</p>
        <p className="text-gray-400 text-xs">{formatRelativeTime(diagnostic.timestamp)}</p>
      </div>
    </div>
  );

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-gray-800 border-l border-gray-700 shadow-2xl z-50 overflow-y-auto">
      <div className="sticky top-0 bg-gray-800 border-b border-gray-700 p-4 flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Node Details</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>
      </div>
      <div className="p-4">
        {node.type === 'device' && renderDeviceDetails(node.data as Device)}
        {node.type === 'alarm' && renderAlarmDetails(node.data as Alarm)}
        {node.type === 'diagnostic' && renderDiagnosticDetails(node.data as Diagnostic)}
      </div>
    </div>
  );
};













