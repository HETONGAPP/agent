/**
 * Site Devices Tab Component
 * Displays and manages site devices
 */

import { Plug, Trash2, Edit } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { formatRelativeTime } from '@/utils/date';
import { Device } from '@/types';

interface SiteDevicesTabProps {
  devices: Device[];
  onAddDevice: () => void;
  onEditDevice: (device: Device) => void;
  onRemoveDevice: (device: Device) => void;
}

export const SiteDevicesTab = ({
  devices,
  onAddDevice,
  onEditDevice,
  onRemoveDevice,
}: SiteDevicesTabProps) => {
  const deviceColumns: Column<Device>[] = [
    {
      key: 'device_id',
      header: 'Device ID',
      render: (device) => (
        <span className="font-mono text-blue-400">{device.device_id}</span>
      ),
    },
    {
      key: 'device_type',
      header: 'Type',
      render: (device) => (
        <Badge type="status" value={device.device_type} size="sm" />
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (device) => (
        <Badge type="status" value={device.status} size="sm" />
      ),
    },
    {
      key: 'integration_name',
      header: 'Brand/Manufacturer',
      render: (device) => {
        const brand = (device.metadata as any)?.brand || 
                     (device.metadata as any)?.manufacturer ||
                     device.integration_name ||
                     'N/A';
        return (
          <span className="text-gray-300">{brand}</span>
        );
      },
    },
    {
      key: 'last_seen',
      header: 'Last Seen',
      render: (device) => (
        <span className="text-gray-400 text-xs">
          {device.last_seen ? formatRelativeTime(device.last_seen) : 'Never'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (device) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEditDevice(device);
            }}
            className="p-1.5 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded transition-colors"
            title="Edit device"
          >
            <Edit size={16} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemoveDevice(device);
            }}
            className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
            title="Remove device"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700/50">
        <h3 className="text-xl font-semibold text-white">Devices</h3>
        <Button
          variant="primary"
          size="sm"
          onClick={onAddDevice}
          className="group hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-200"
        >
          <Plug size={16} className="mr-2 group-hover:scale-110 transition-transform" />
          Add Device
        </Button>
      </div>
      {devices.length > 0 ? (
        <DataTable data={devices} columns={deviceColumns} />
      ) : (
        <div className="text-center py-16">
          <Plug size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 text-lg mb-2">No devices found</p>
          <p className="text-gray-500 text-sm">Add your first device to get started</p>
        </div>
      )}
    </div>
  );
};

