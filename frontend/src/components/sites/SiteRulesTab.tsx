/**
 * Site Rules Tab Component
 * Displays and manages site rules
 */

import { useState, useMemo, useCallback, useEffect } from 'react';
import { AlertCircle, Edit, Trash2, Filter, Power, PowerOff } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { FilterBar } from '@/components/ui/FilterBar';
import { Pagination } from '@/components/ui/Pagination';
import { deleteSiteRule, updateSiteRule } from '@/api/sites';

// All supported device types
const ALL_DEVICE_TYPES = [
  'BMS',
  'PCS',
  'UPS',
  'TMS',
  'EMS',
  'METER',
  'TRANSFORMER',
  'GSB',
  'SPPC',
  'EVCS',
  'FAN',
  'HVAC',
  'HTS',
  'FMS',
  'GENSET',
  'DATALOGGER',
  'MONITORING',
  'BESS',
  'ESS',
  'EMS', // For site-level rules
  'OTHER',
];

interface SiteRulesTabProps {
  siteId: string | undefined;
  siteRules: any;
  devices: any[];
  onAddRule: () => void;
  onEditRule: (rule: any) => void;
  onRefreshRules: () => void;
  onToast: (message: string, type: 'success' | 'error') => void;
}

export const SiteRulesTab = ({
  siteId,
  siteRules,
  devices,
  onAddRule,
  onEditRule,
  onRefreshRules,
  onToast,
}: SiteRulesTabProps) => {
  const [selectedDeviceType, setSelectedDeviceType] = useState<string>('');
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 15;
  
  const siteRulesData = siteId ? (siteRules[siteId] || null) : null;
  const deviceRules = siteRulesData?.devices || [];
  const unassignedRules = siteRulesData?.unassigned_rules || [];
  
  // Flatten rules into table rows: one row per rule
  // First, add device-specific rules
  const deviceRulesData = useMemo(() => {
    return deviceRules.flatMap((deviceRule: any) => 
      (deviceRule.rules || []).map((rule: any, index: number) => {
        const condition = rule.condition || {};
        return {
          device_id: deviceRule.device_id,
          device_name: deviceRule.device_name,
          device_type: deviceRule.device_type,
          rule_id: rule.id || `rule_${deviceRule.device_id}_${index}`,
          rule_name: rule.name || rule.id || `Rule ${index + 1}`,
          rule_description: rule.description || '',
          rule_priority: rule.priority ?? 0,
          rule_severity: rule.severity || '',
          rule_condition: rule.condition ? JSON.stringify(rule.condition) : '',
          rule_value: condition.value ?? '-',
          rule_operator: condition.operator || '',
          rule_unit: condition.unit || '',
          rule_enabled: rule.enabled !== false, // Default to true if not specified
          fullRule: rule,
        };
      })
    );
  }, [deviceRules]);
  
  // Then, add unassigned rules (site-level, multi-device rules)
  // EMS rules should have device_id as "GLOBAL"
  const unassignedRulesData = useMemo(() => {
    return unassignedRules.map((rule: any, index: number) => {
      const ruleDeviceTypes = rule.device_types || [];
      const isEMS = ruleDeviceTypes.includes('EMS');
      const condition = rule.condition || {};
      return {
        device_id: isEMS ? 'GLOBAL' : '-',
        device_name: isEMS ? 'Global (EMS)' : 'Site Level',
        device_type: ruleDeviceTypes.join(', ') || 'EMS',
        rule_id: rule.id || `rule_unassigned_${index}`,
        rule_name: rule.name || rule.id || `Rule ${index + 1}`,
        rule_description: rule.description || '',
        rule_priority: rule.priority ?? 0,
        rule_severity: rule.severity || '',
        rule_condition: rule.condition ? JSON.stringify(rule.condition) : '',
        rule_value: condition.value ?? '-',
        rule_operator: condition.operator || '',
        rule_unit: condition.unit || '',
        rule_enabled: rule.enabled !== false, // Default to true if not specified
        fullRule: rule,
      };
    });
  }, [unassignedRules]);
  
  // Combine all rules and sort by priority (desc) then by rule_id for stable ordering
  const allRulesTableData = useMemo(() => {
    const combined = [...deviceRulesData, ...unassignedRulesData];
    // Sort by priority (descending) then by rule_id (ascending) for stable ordering
    return combined.sort((a, b) => {
      const priorityDiff = (b.rule_priority || 0) - (a.rule_priority || 0);
      if (priorityDiff !== 0) return priorityDiff;
      // If priority is the same, sort by rule_id for stable ordering
      return (a.rule_id || '').localeCompare(b.rule_id || '');
    });
  }, [deviceRulesData, unassignedRulesData]);
  
  // Filter rules by device type and device ID
  const rulesTableData = useMemo(() => {
    let filtered = allRulesTableData;
    
    // Filter by device type
    if (selectedDeviceType) {
      filtered = filtered.filter((rule) => {
        // For site-level/unassigned rules (including GLOBAL/EMS), check if they apply to the selected device type
        if (rule.device_id === '-' || rule.device_id === 'GLOBAL') {
          if (rule.fullRule && rule.fullRule.device_types) {
            return rule.fullRule.device_types.includes(selectedDeviceType);
          }
          return false;
        }
        
        // For device-specific rules, check device_type
        if (rule.device_type && rule.device_type !== 'EMS' && rule.device_type !== '-') {
          try {
            const deviceTypes = rule.device_type.split(',').map((t: string) => t.trim());
            return deviceTypes.includes(selectedDeviceType);
          } catch (error) {
            return rule.device_type === selectedDeviceType;
          }
        }
        
        return false;
      });
    }
    
    // Filter by device ID
    if (selectedDeviceId) {
      filtered = filtered.filter((rule) => {
        if (rule.device_id === '-' || rule.device_id === 'GLOBAL') {
          return false; // Exclude site-level and global rules when filtering by device ID
        }
        return rule.device_id === selectedDeviceId;
      });
    }
    
    return filtered;
  }, [allRulesTableData, selectedDeviceType, selectedDeviceId]);

  // Paginate filtered rules
  const paginatedRules = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return rulesTableData.slice(startIndex, endIndex);
  }, [rulesTableData, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(rulesTableData.length / itemsPerPage);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedDeviceType, selectedDeviceId]);
  
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };
  
  const handleClearFilters = () => {
    setSelectedDeviceType('');
    setSelectedDeviceId('');
  };
  
  // Get unique device IDs from both rules and devices prop for device filter (filtered by selected device type)
  const availableDeviceIds = useMemo(() => {
    const deviceIds = new Set<string>();
    
    // First, add device IDs from devices prop (all devices in the site)
    devices.forEach((device: any) => {
      const deviceId = device.device_id;
      const deviceType = String(device.device_type || '').toUpperCase().trim();
      
      // Skip EMS devices
      if (deviceType === 'EMS') {
        return;
      }
      
      // If device type filter is selected, only include matching devices
      if (selectedDeviceType) {
        if (deviceType === selectedDeviceType) {
          deviceIds.add(deviceId);
        }
      } else {
        // No filter, include all devices
        deviceIds.add(deviceId);
      }
    });
    
    // Also add device IDs from rules (in case some devices have rules but aren't in devices prop)
    let sourceData = allRulesTableData;
    
    // If device type is selected, filter by device type first
    if (selectedDeviceType) {
      sourceData = allRulesTableData.filter((rule) => {
        if (rule.device_id === '-' || rule.device_id === 'GLOBAL') return false;
        if (rule.device_type && rule.device_type !== 'EMS' && rule.device_type !== '-') {
          try {
            const deviceTypes = rule.device_type.split(',').map((t: string) => t.trim());
            return deviceTypes.includes(selectedDeviceType);
          } catch (error) {
            return rule.device_type === selectedDeviceType;
          }
        }
        return false;
      });
    }
    
    sourceData.forEach((rule) => {
      if (rule.device_id && rule.device_id !== '-' && rule.device_id !== 'GLOBAL') {
        deviceIds.add(rule.device_id);
      }
    });
    
    return Array.from(deviceIds).sort();
  }, [allRulesTableData, selectedDeviceType, devices]);
  
  if (!siteRulesData) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700/50">
          <div className="flex items-center gap-3">
            <AlertCircle className="text-yellow-400" size={20} />
            <h3 className="text-xl font-semibold text-white">Rules</h3>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={onAddRule}
            className="group hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-200"
          >
            <AlertCircle size={16} className="mr-2 group-hover:scale-110 transition-transform" />
            Add Rule
          </Button>
        </div>
        <div className="text-center py-16">
          <AlertCircle size={48} className="mx-auto text-gray-600 mb-4" />
          <p className="text-gray-400 text-lg mb-2">No rules configured</p>
          <p className="text-gray-500 text-sm">Rules configuration will be displayed here</p>
        </div>
      </div>
    );
  }
  
  // Helper function to get unit from row
  const getUnit = useCallback((row: any) => {
    let unit = row.rule_unit;
    const condition = row.fullRule?.condition || {};
    const field = condition.field || '';
    
    // If unit is missing, try to infer from field name
    if (!unit && field) {
      const fieldLower = field.toLowerCase();
      if (fieldLower.includes('soc') || fieldLower.includes('soh')) {
        unit = '%';
      } else if (fieldLower.includes('temperature') || fieldLower.includes('temp')) {
        unit = '°C';
      } else if (fieldLower.includes('voltage') || fieldLower.includes('voltage')) {
        unit = 'V';
      } else if (fieldLower.includes('current')) {
        unit = 'A';
      } else if (fieldLower.includes('power')) {
        unit = 'kW';
      } else if (fieldLower.includes('energy')) {
        unit = 'kWh';
      } else if (fieldLower.includes('frequency')) {
        unit = 'Hz';
      }
    }
    
    return unit || '';
  }, []);

  // Memoize columns to prevent re-creation on every render
  const rulesColumns: Column<any>[] = useMemo(() => [
    {
      key: 'device_id',
      header: 'Device ID',
      width: '15%',
      render: (row) => {
        if (row.device_id === 'GLOBAL') {
          return <span className="font-mono text-green-400 font-semibold">GLOBAL</span>;
        }
        return <span className="font-mono text-blue-400">{row.device_id}</span>;
    },
    },
    {
      key: 'device_type',
      header: 'Device Type',
      width: '12%',
      render: (row) => (
        <Badge type="status" value={row.device_type} size="sm" />
      ),
    },
    {
      key: 'rule_name',
      header: 'Rule Name',
      width: '25%',
      render: (row) => (
        <span className="text-white">{row.rule_name}</span>
      ),
    },
    {
      key: 'rule_priority',
      header: 'Priority',
      width: '10%',
      render: (row) => {
        const priority = row.rule_priority ?? 0;
        const getPriorityColor = () => {
          if (priority >= 8) return 'bg-red-500/20 text-red-400 border-red-500/50';
          if (priority >= 5) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
          return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
        };
        return (
          <span className={`badge border px-2 py-0.5 text-xs ${getPriorityColor()}`}>
            {priority}
          </span>
        );
      },
    },
    {
      key: 'rule_severity',
      header: 'Severity',
      width: '12%',
      render: (row) => (
        row.rule_severity ? (
          <Badge 
            type="severity"
            value={row.rule_severity}
            size="sm"
          />
        ) : (
          <span className="text-gray-500">-</span>
        )
      ),
    },
    {
      key: 'rule_value',
      header: 'Value',
      width: '10%',
      render: (row) => {
        const value = row.rule_value;
        
        if (value === '-' || value === null || value === undefined) {
          return <span className="text-gray-500">-</span>;
        }
        
        const displayValue = typeof value === 'number' ? value.toString() : String(value);
        
        return (
          <span className="font-mono text-cyan-400">
            {displayValue}
          </span>
        );
      },
    },
    {
      key: 'rule_unit',
      header: 'Unit',
      width: '8%',
      hideOnMobile: true,
      render: (row) => {
        const unit = getUnit(row);
        
        if (!unit) {
          return <span className="text-gray-500">-</span>;
        }
        
        return (
          <span className="text-gray-400 text-sm">
            {unit}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '18%',
      render: (row) => {
        const isEnabled = row.rule_enabled !== false;
        
        return (
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                if (!siteId || !row.fullRule) return;
                
                try {
                  const updatedRule = {
                    ...row.fullRule,
                    enabled: !isEnabled,
                  };
                  
                  const response = await updateSiteRule(siteId, row.rule_id, updatedRule);
                  if (response.status === 'success') {
                    onToast(`Rule ${isEnabled ? 'disabled' : 'enabled'} successfully`, 'success');
                    onRefreshRules();
                  } else {
                    onToast(response.message || 'Failed to update rule', 'error');
                  }
                } catch (error: any) {
                  onToast(error?.response?.data?.message || error?.message || 'Failed to update rule', 'error');
                }
              }}
              className={`p-1.5 rounded transition-colors ${
                isEnabled
                  ? 'text-green-400 hover:text-green-300 hover:bg-green-500/10'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-500/10'
              }`}
              title={isEnabled ? 'Disable rule' : 'Enable rule'}
            >
              {isEnabled ? <Power size={16} /> : <PowerOff size={16} />}
            </button>
            <button
              onClick={() => {
                if (row.fullRule) {
                  onEditRule({ ...row.fullRule, device_id: row.device_id, device_type: row.device_type });
                }
              }}
              className="p-1.5 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded transition-colors"
              title="Edit rule"
            >
              <Edit size={16} />
            </button>
            <button
              onClick={async () => {
                if (window.confirm(`Are you sure you want to delete rule "${row.rule_id}"?`)) {
                  try {
                    const response = await deleteSiteRule(siteId!, row.rule_id);
                    if (response.status === 'success') {
                      onToast(`Rule ${row.rule_id} deleted successfully`, 'success');
                      onRefreshRules();
                    } else {
                      onToast(response.message || 'Failed to delete rule', 'error');
                    }
                  } catch (error: any) {
                    onToast(error?.response?.data?.message || error?.message || 'Failed to delete rule', 'error');
                  }
                }
              }}
              className="p-1.5 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
              title="Delete rule"
            >
              <Trash2 size={16} />
            </button>
          </div>
        );
      },
    },
  ], [onEditRule, siteId, onToast, onRefreshRules, getUnit]);
  
  // Get device types that have rules (only show device types with existing rules)
  const availableDeviceTypes = useMemo(() => {
    const types = new Set<string>();
    
    // Add device types from deviceRules (devices that have rules assigned)
    deviceRules.forEach((deviceRule: any) => {
      if (deviceRule.device_type && deviceRule.rules && deviceRule.rules.length > 0) {
        const deviceType = String(deviceRule.device_type).toUpperCase().trim();
        if (deviceType && deviceType !== 'EMS') {
          types.add(deviceType);
        }
      }
    });
    
    // Add device types from flattened rules data (rules that are assigned to devices)
    allRulesTableData.forEach((rule) => {
      // Only include rules that are assigned to devices (not site-level or global)
      if (rule.device_id && rule.device_id !== '-' && rule.device_id !== 'GLOBAL' && rule.device_type && rule.device_type !== 'EMS') {
        try {
          // Handle comma-separated device types
          rule.device_type.split(',').forEach((t: string) => {
            const trimmed = t.trim().toUpperCase();
            if (trimmed && trimmed !== 'EMS') {
              types.add(trimmed);
            }
          });
        } catch (error) {
          // If split fails, just add the device_type as is
          if (rule.device_type && rule.device_type !== 'EMS') {
            types.add(String(rule.device_type).toUpperCase().trim());
          }
        }
      }
    });
    
    // Convert to array and sort
    return Array.from(types).sort();
  }, [allRulesTableData, deviceRules]);
  
  return (
    <div className="card w-full max-w-full min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 sm:mb-6 pb-4 border-b border-gray-700/50">
        <div className="flex items-center gap-3 min-w-0">
          <AlertCircle className="text-yellow-400 shrink-0" size={20} />
          <h3 className="text-lg sm:text-xl font-semibold text-white truncate">Rules</h3>
          {rulesTableData.length > 0 && (
            <span className="shrink-0">
              <Badge type="status" value={`${rulesTableData.length} rules`} size="sm" />
            </span>
          )}
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={onAddRule}
          className="group hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-200 shrink-0 w-full sm:w-auto"
        >
          <AlertCircle size={16} className="mr-2 group-hover:scale-110 transition-transform" />
          Add Rule
        </Button>
      </div>
      
      {/* Filter Bar */}
      <FilterBar
        showClear={false}
      >
        <div className="flex flex-wrap items-center gap-3 sm:gap-4 min-w-0">
          <div className="flex items-center gap-2 min-w-0 w-full sm:w-auto">
            <Filter size={16} className="text-gray-400 shrink-0" />
            <label className="text-sm text-gray-400 whitespace-nowrap shrink-0">Device Type:</label>
            <select
              value={selectedDeviceType}
              onChange={(e) => {
                setSelectedDeviceType(e.target.value);
                setSelectedDeviceId(''); // Reset device ID filter when device type changes
              }}
              className="flex-1 min-w-0 max-w-full sm:min-w-[150px] px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Device Types</option>
              {availableDeviceTypes.length > 0 ? (
                availableDeviceTypes.map((deviceType) => (
                  <option key={deviceType} value={deviceType}>
                    {deviceType}
                  </option>
                ))
              ) : (
                <option value="" disabled>No device types available</option>
              )}
            </select>
          </div>
          
          <div className="flex items-center gap-2 min-w-0 w-full sm:w-auto">
            <label className="text-sm text-gray-400 whitespace-nowrap shrink-0">Device:</label>
            <select
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              className="flex-1 min-w-0 max-w-full sm:min-w-[150px] px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={!selectedDeviceType && availableDeviceIds.length === 0}
            >
              <option value="">All Devices</option>
              {availableDeviceIds.map((deviceId) => {
                const device = devices.find(d => d.device_id === deviceId);
                return (
                  <option key={deviceId} value={deviceId}>
                    {deviceId} {device?.device_name ? `(${device.device_name})` : ''}
                  </option>
                );
              })}
            </select>
          </div>
        </div>
      </FilterBar>
      
      <DataTable data={paginatedRules} columns={rulesColumns} />
      
      {/* Pagination */}
      {rulesTableData.length > 0 && (
        <div className="mt-4">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={rulesTableData.length}
            itemsPerPage={itemsPerPage}
            onPageChange={handlePageChange}
          />
        </div>
      )}
    </div>
  );
};







