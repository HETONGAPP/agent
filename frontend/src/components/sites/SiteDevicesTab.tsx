/**
 * Site Devices Tab Component
 * Displays and manages site devices
 */

import { useState, useMemo, useEffect } from 'react';
import { Plug, Trash2, Edit, Filter } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { formatRelativeTime } from '@/utils/date';
import { Device } from '@/types';
import { DEVICE_STATUS } from '@/config/constants';

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
  const [selectedDeviceType, setSelectedDeviceType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 15;

  // Get unique device types from devices
  const availableDeviceTypes = useMemo(() => {
    const types = new Set<string>();
    devices.forEach((device) => {
      if (device.device_type) {
        types.add(device.device_type);
      }
    });
    return Array.from(types).sort();
  }, [devices]);

  // Filter devices
  const filteredDevices = useMemo(() => {
    return devices.filter((device) => {
      // Filter by device type
      if (selectedDeviceType && device.device_type !== selectedDeviceType) {
        return false;
      }
      
      // Filter by status
      if (selectedStatus && device.status !== selectedStatus) {
        return false;
      }
      
      return true;
    });
  }, [devices, selectedDeviceType, selectedStatus]);

  // Paginate filtered devices
  const paginatedDevices = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredDevices.slice(startIndex, endIndex);
  }, [filteredDevices, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(filteredDevices.length / itemsPerPage);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedDeviceType, selectedStatus]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

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
        <div className="flex items-center gap-3">
          <Plug className="text-blue-400" size={20} />
          <h3 className="text-xl font-semibold text-white">Devices</h3>
          {filteredDevices.length > 0 && (
            <Badge type="status" value={`${filteredDevices.length} devices`} size="sm" />
          )}
        </div>
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

      {/* Filter Bar */}
      <FilterBar
        showClear={false}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-gray-400" />
            <label className="text-sm text-gray-400 whitespace-nowrap">Device Type:</label>
            <select
              value={selectedDeviceType}
              onChange={(e) => setSelectedDeviceType(e.target.value)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
            >
              <option value="">All Device Types</option>
              {availableDeviceTypes.map((deviceType) => (
                <option key={deviceType} value={deviceType}>
                  {deviceType}
                </option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400 whitespace-nowrap">Status:</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[150px]"
            >
              <option value="">All Statuses</option>
              {Object.entries(DEVICE_STATUS).map(([key, value]) => (
                <option key={key} value={value}>
                  {key}
                </option>
              ))}
            </select>
          </div>
        </div>
      </FilterBar>

      {filteredDevices.length > 0 ? (
        <>
          <DataTable data={paginatedDevices} columns={deviceColumns} />
          {/* Pagination */}
          {filteredDevices.length > 0 && (
            <div className="mt-4">
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={filteredDevices.length}
                itemsPerPage={itemsPerPage}
                onPageChange={handlePageChange}
              />
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-16">
          <Plug size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 text-lg mb-2">No devices found</p>
          <p className="text-gray-500 text-sm">
            {devices.length === 0 
              ? 'Add your first device to get started'
              : 'No devices match the current filters'}
          </p>
        </div>
      )}
    </div>
  );
};

