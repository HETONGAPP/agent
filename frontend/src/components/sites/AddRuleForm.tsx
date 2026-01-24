/**
 * Add Rule Form Component
 * Form for adding a rule to a site
 */

import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useToastStore } from '@/store/useToastStore';
import { addSiteRule } from '@/api/sites';
import { Trash2 } from 'lucide-react';

// All supported device types (from backend DeviceType enum)
// Universal support for all energy storage system components
const ALL_DEVICE_TYPES = [
  // Core Energy Storage Components
  'BMS',      // Battery Management System
  'PCS',      // Power Conversion System (includes Storage/PV/Generic inverters)
  'UPS',      // Uninterruptible Power Supply
  'TMS',      // Thermal Management System
  'EMS',      // Energy Management System
  
  // Power System Components
  'METER',    // Power Meter
  'TRANSFORMER', // Transformer
  'GSB',      // Grid Service Breaker
  'SPPC',     // Smart Power Point Controller
  
  // Charging and Load Management
  'EVCS',     // Electric Vehicle Charging Station
  
  // Environmental Control
  'FAN',      // Fan/Cooling Fan
  'HVAC',     // Heating, Ventilation, and Air Conditioning
  
  // Monitoring and Sensors
  'HTS',      // Humidity/Temperature Sensor
  
  // Safety and Backup
  'FMS',      // Fire Management System
  'GENSET',   // Generator Set
  
  // Data and Communication
  'DATALOGGER', // Data Logger
  'MONITORING', // Monitoring System
  
  // Aggregation
  'BESS',     // Battery Energy Storage System (aggregated)
  'ESS',     // Energy Storage System (aggregated)
  
  // Other
  'OTHER',    // Other components
];

// Device type to available fields mapping
const DEVICE_TYPE_FIELDS: Record<string, Array<{ value: string; label: string; description?: string }>> = {
  BMS: [
    { value: 'soc', label: 'SOC (State of Charge)', description: 'Battery charge percentage (0-100)' },
    { value: 'soh', label: 'SOH (State of Health)', description: 'Battery health percentage (0-100)' },
    { value: 'max_delta_v', label: 'Max Delta V', description: 'Maximum voltage difference between cells (V)' },
    { value: 'max_voltage', label: 'Max Voltage', description: 'Maximum cell voltage (V)' },
    { value: 'min_voltage', label: 'Min Voltage', description: 'Minimum cell voltage (V)' },
    { value: 'max_temperature', label: 'Max Temperature', description: 'Maximum temperature (°C)' },
    { value: 'min_temperature', label: 'Min Temperature', description: 'Minimum temperature (°C)' },
    { value: 'cell_voltages', label: 'Cell Voltages', description: 'Array of individual cell voltages' },
    { value: 'temperatures', label: 'Temperatures', description: 'Array of temperature readings' },
  ],
  PCS: [
    { value: 'dc_voltage', label: 'DC Voltage', description: 'DC input voltage (V)' },
    { value: 'ac_voltage', label: 'AC Voltage', description: 'AC output voltage (V)' },
    { value: 'active_power', label: 'Active Power', description: 'Active power output (kW)' },
    { value: 'reactive_power', label: 'Reactive Power', description: 'Reactive power output (kVAR)' },
    { value: 'voltage', label: 'Voltage', description: 'AC voltage (V)' },
    { value: 'current', label: 'Current', description: 'AC current (A)' },
    { value: 'frequency', label: 'Frequency', description: 'AC frequency (Hz)' },
    { value: 'efficiency', label: 'Efficiency', description: 'Conversion efficiency (%)' },
    { value: 'temperature', label: 'Temperature', description: 'Operating temperature (°C)' },
    { value: 'operating_state', label: 'Operating State', description: 'PCS operating state' },
    { value: 'grid_connection_status', label: 'Grid Connection Status', description: 'Grid connection state (connected/disconnected)' },
    { value: 'status', label: 'Status', description: 'Operating status (running/stopped/fault)' },
  ],
  UPS: [
    { value: 'input_voltage', label: 'Input Voltage', description: 'Input AC voltage (V)' },
    { value: 'output_voltage', label: 'Output Voltage', description: 'Output AC voltage (V)' },
    { value: 'battery_voltage', label: 'Battery Voltage', description: 'Battery pack voltage (V)' },
    { value: 'load_percentage', label: 'Load Percentage', description: 'Current load percentage (%)' },
    { value: 'battery_capacity', label: 'Battery Capacity', description: 'Battery capacity percentage (%)' },
    { value: 'temperature', label: 'Temperature', description: 'Operating temperature (°C)' },
    { value: 'status', label: 'Status', description: 'Operating status (normal/battery/bypass/fault)' },
  ],
  TMS: [
    { value: 'ambient_temperature', label: 'Ambient Temperature', description: 'Ambient air temperature (°C)' },
    { value: 'coolant_temperature', label: 'Coolant Temperature', description: 'Coolant temperature (°C)' },
    { value: 'coolant_flow_rate', label: 'Coolant Flow Rate', description: 'Coolant flow rate (L/min)' },
    { value: 'fan_speed', label: 'Fan Speed', description: 'Fan rotation speed (RPM)' },
    { value: 'cooling_system_status', label: 'Cooling System Status', description: 'Cooling system operating status' },
    { value: 'pump_status', label: 'Pump Status', description: 'Pump operating status (running/stopped/fault)' },
  ],
  EMS: [
    { value: 'total_power', label: 'Total Power', description: 'Total system power (kW)' },
    { value: 'energy_consumption', label: 'Energy Consumption', description: 'Total energy consumption (kWh)' },
    { value: 'status', label: 'Status', description: 'System status' },
  ],
  METER: [
    { value: 'voltage', label: 'Voltage', description: 'AC voltage (V)' },
    { value: 'voltage_a', label: 'Voltage Phase A', description: 'Phase A voltage (V)' },
    { value: 'voltage_b', label: 'Voltage Phase B', description: 'Phase B voltage (V)' },
    { value: 'voltage_c', label: 'Voltage Phase C', description: 'Phase C voltage (V)' },
    { value: 'current', label: 'Current', description: 'AC current (A)' },
    { value: 'frequency', label: 'Frequency', description: 'AC frequency (Hz)' },
    { value: 'active_power', label: 'Active Power', description: 'Active power (kW)' },
    { value: 'active_production_energy', label: 'Active Production Energy', description: 'Total production energy (kWh)' },
    { value: 'active_consumption_energy', label: 'Active Consumption Energy', description: 'Total consumption energy (kWh)' },
    { value: 'communication_status', label: 'Communication Status', description: 'Communication status' },
  ],
  EVCS: [
    { value: 'active_power', label: 'Active Power', description: 'Charging power (kW)' },
    { value: 'soc', label: 'SOC', description: 'Vehicle battery state of charge (%)' },
    { value: 'connector_status', label: 'Connector Status', description: 'Connector status' },
    { value: 'temperature', label: 'Temperature', description: 'Operating temperature (°C)' },
    { value: 'total_energy_ac', label: 'Total Energy AC', description: 'Total AC energy (kWh)' },
    { value: 'total_energy_dc', label: 'Total Energy DC', description: 'Total DC energy (kWh)' },
  ],
  FAN: [
    { value: 'status', label: 'Status', description: 'Device status (normal/fault/warning)' },
    { value: 'state', label: 'State', description: 'Operating state (running/standby/fault)' },
    { value: 'speed', label: 'Speed', description: 'Fan rotation speed (RPM)' },
    { value: 'vendor_state', label: 'Vendor State', description: 'Vendor-specific state' },
  ],
  HVAC: [
    { value: 'status', label: 'Status', description: 'Device status (normal/fault)' },
    { value: 'state', label: 'State', description: 'Operating state (running/standby/fault)' },
    { value: 'inside_temp', label: 'Inside Temperature', description: 'Inside temperature (°C)' },
    { value: 'outside_temp', label: 'Outside Temperature', description: 'Outside temperature (°C)' },
    { value: 'humidity', label: 'Humidity', description: 'Humidity (%)' },
    { value: 'communication_status', label: 'Communication Status', description: 'Communication status' },
  ],
  HTS: [
    { value: 'temperature', label: 'Temperature', description: 'Temperature reading (°C)' },
    { value: 'humidity', label: 'Humidity', description: 'Humidity reading (%)' },
    { value: 'communication_status', label: 'Communication Status', description: 'Communication status' },
  ],
  GENSET: [
    { value: 'status', label: 'Status', description: 'Device status (normal/fault)' },
    { value: 'temperature', label: 'Temperature', description: 'Operating temperature (°C)' },
    { value: 'oil_pressure', label: 'Oil Pressure', description: 'Oil pressure (psi)' },
    { value: 'active_power', label: 'Active Power', description: 'Generator output power (kW)' },
    { value: 'frequency', label: 'Frequency', description: 'Output frequency (Hz)' },
    { value: 'voltage', label: 'Voltage', description: 'Output voltage (V)' },
  ],
  FMS: [
    { value: 'status', label: 'Status', description: 'Device status (normal/alarm/fault)' },
    { value: 'state', label: 'State', description: 'System state' },
    { value: 'vendor_state', label: 'Vendor State', description: 'Vendor-specific state' },
  ],
  DATALOGGER: [
    { value: 'communication_status', label: 'Communication Status', description: 'Communication status' },
    { value: 'data_stale', label: 'Data Stale', description: 'Data staleness indicator' },
    { value: 'active_power', label: 'Active Power', description: 'Logged active power (kW)' },
    { value: 'active_production_energy', label: 'Active Production Energy', description: 'Total production energy (kWh)' },
  ],
  GSB: [
    { value: 'status', label: 'Status', description: 'Grid service breaker status' },
    { value: 'grid_voltage_phase_l1', label: 'Grid Voltage Phase L1', description: 'Grid voltage phase L1 (V)' },
    { value: 'grid_voltage_phase_l2', label: 'Grid Voltage Phase L2', description: 'Grid voltage phase L2 (V)' },
    { value: 'grid_voltage_phase_l3', label: 'Grid Voltage Phase L3', description: 'Grid voltage phase L3 (V)' },
    { value: 'grid_breaker_position', label: 'Grid Breaker Position', description: 'Grid breaker position' },
  ],
  SPPC: [
    { value: 'load_limit_setpoint', label: 'Load Limit Setpoint', description: 'Load limit setpoint (kW)' },
    { value: 'status', label: 'Status', description: 'Device status' },
  ],
  TRANSFORMER: [
    { value: 'primary_voltage', label: 'Primary Voltage', description: 'Primary winding voltage (V)' },
    { value: 'secondary_voltage', label: 'Secondary Voltage', description: 'Secondary winding voltage (V)' },
    { value: 'load', label: 'Load', description: 'Load percentage (%)' },
    { value: 'temperature', label: 'Temperature', description: 'Operating temperature (°C)' },
  ],
  MONITORING: [
    { value: 'status', label: 'Status', description: 'Monitoring system status' },
    { value: 'data_quality', label: 'Data Quality', description: 'Data quality indicator' },
  ],
  BESS: [
    { value: 'soc', label: 'SOC', description: 'Overall battery state of charge (%)' },
    { value: 'active_power', label: 'Active Power', description: 'Total active power (kW)' },
    { value: 'max_charge_power_limit', label: 'Max Charge Power Limit', description: 'Maximum charge power limit (kW)' },
    { value: 'max_discharge_power_limit', label: 'Max Discharge Power Limit', description: 'Maximum discharge power limit (kW)' },
  ],
  ESS: [
    { value: 'soc', label: 'SOC', description: 'Overall battery state of charge (%)' },
    { value: 'active_power', label: 'Active Power', description: 'Total active power (kW)' },
    { value: 'max_charge_power_limit', label: 'Max Charge Power Limit', description: 'Maximum charge power limit (kW)' },
    { value: 'max_discharge_power_limit', label: 'Max Discharge Power Limit', description: 'Maximum discharge power limit (kW)' },
  ],
  OTHER: [
    { value: 'status', label: 'Status', description: 'Device status' },
    { value: 'value', label: 'Value', description: 'Generic numeric value' },
  ],
};

interface AddRuleFormProps {
  siteId: string;
  devices: Array<{ device_id: string; device_type: string; device_name?: string }>;
  initialRule?: any; // For editing existing rule
  onSuccess?: (ruleData?: any) => void; // Pass ruleData for editing mode
  onCancel?: () => void;
  onDelete?: (ruleId: string) => void; // Callback for deleting rule
}

export const AddRuleForm = ({ siteId, devices, initialRule, onSuccess, onCancel, onDelete }: AddRuleFormProps) => {
  const { addToast } = useToastStore();
  
  // Safely initialize form data with proper defaults
  const getInitialFormData = () => {
    if (!initialRule) {
      return {
        id: '',
        name: '',
        description: '',
        device_type: '',
        device_id: '',
        condition_type: 'threshold',
        condition_field: '',
        condition_operator: '>',
        condition_value: '',
        severity: 'Warning',
        priority: '5',
        actions: [
          { name: 'trigger_llm_diagnostic', enabled: true },
          { name: 'send_email', enabled: false },
          { name: 'notify_engineer', enabled: false },
          { name: 'log_alarm', enabled: true },
        ],
      };
    }
    
    // Handle device_type and device_id from different possible sources
    let device_type = '';
    let device_id = '';
    
    if (initialRule.device_types && initialRule.device_types.length > 0) {
      device_type = initialRule.device_types[0];
    } else if (initialRule.device_type) {
      device_type = initialRule.device_type;
    }
    
    if (initialRule.device_ids && initialRule.device_ids.length > 0) {
      device_id = initialRule.device_ids[0];
    } else if (initialRule.device_id) {
      device_id = initialRule.device_id;
    }
    
    // Parse actions from initialRule
    let actions = [
      { name: 'trigger_llm_diagnostic', enabled: true },
      { name: 'send_email', enabled: false },
      { name: 'notify_engineer', enabled: false },
      { name: 'log_alarm', enabled: true },
    ];
    
    if (initialRule.actions && Array.isArray(initialRule.actions)) {
      // Map existing actions to our format
      const actionMap = new Map();
      initialRule.actions.forEach((action: any) => {
        if (typeof action === 'string') {
          actionMap.set(action, { name: action, enabled: true });
        } else if (action.name) {
          actionMap.set(action.name, { name: action.name, enabled: action.enabled !== false });
        }
      });
      
      // Update default actions with existing values
      actions = actions.map(defaultAction => {
        if (actionMap.has(defaultAction.name)) {
          return actionMap.get(defaultAction.name);
        }
        return defaultAction;
      });
    }
    
    return {
      id: initialRule.id || '',
      name: initialRule.name || '',
      description: initialRule.description || '',
      device_type: device_type,
      device_id: device_id,
      condition_type: initialRule.condition?.type || 'threshold',
      condition_field: initialRule.condition?.field || '',
      condition_operator: initialRule.condition?.operator || '>',
      condition_value: initialRule.condition?.value?.toString() || '',
      severity: initialRule.severity || 'Warning',
      priority: initialRule.priority?.toString() || '5',
      actions: actions,
    };
  };
  
  const [formData, setFormData] = useState(getInitialFormData());
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      // Build rule object
      const ruleData: any = {
        id: formData.id,
        name: formData.name || formData.id,
        description: formData.description || '',
        condition: {
          type: formData.condition_type,
          field: formData.condition_field,
          operator: formData.condition_operator,
          value: formData.condition_type === 'threshold' ? parseFloat(formData.condition_value) : formData.condition_value,
        },
        severity: formData.severity,
        priority: parseInt(formData.priority, 10),
      };

      // Add device filters if specified
      if (formData.device_type) {
        ruleData.device_types = [formData.device_type];
      }
      if (formData.device_id) {
        ruleData.device_ids = [formData.device_id];
      }
      
      // Add actions (include all actions with enabled status)
      if (formData.actions && Array.isArray(formData.actions)) {
        ruleData.actions = formData.actions.map((action: any) => ({
          name: action.name,
          enabled: action.enabled,
        }));
      }

      // If editing, pass ruleData to onSuccess callback (parent will handle API call)
      if (initialRule) {
        if (onSuccess) {
          onSuccess(ruleData);
        }
      } else {
        // Adding new rule
        const response = await addSiteRule(siteId, ruleData);

        if (response.status === 'success') {
          addToast(`Rule ${formData.id} added successfully`, 'success');
          if (onSuccess) {
            onSuccess();
          }
        } else {
          addToast(response.message || 'Failed to add rule', 'error');
        }
      }
    } catch (error: any) {
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to add rule';
      addToast(errorMessage, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  // Filter devices by selected device type
  const filteredDevices = formData.device_type
    ? devices.filter(d => d.device_type === formData.device_type)
    : devices;

  // Get available fields for selected device type
  const availableFields = formData.device_type 
    ? (DEVICE_TYPE_FIELDS[formData.device_type] || [])
    : [];
  
  // If no device type selected, show common fields
  const commonFields = [
    { value: 'voltage', label: 'Voltage', description: 'Voltage measurement (V)' },
    { value: 'current', label: 'Current', description: 'Current measurement (A)' },
    { value: 'temperature', label: 'Temperature', description: 'Temperature measurement (°C)' },
    { value: 'status', label: 'Status', description: 'Device status' },
  ];
  
  const fieldsToShow = formData.device_type ? availableFields : commonFields;

  // Use all supported device types (not just devices in current site)
  // This allows creating rules for device types that don't have devices yet
  const availableDeviceTypes = ALL_DEVICE_TYPES;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Rule ID <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          name="id"
          value={formData.id}
          onChange={handleChange}
          required
          disabled={!!initialRule} // Disable ID editing for existing rules
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          placeholder="RULE_001"
        />
        {initialRule && (
          <p className="text-xs text-gray-500 mt-1">Rule ID cannot be changed</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Rule Name
        </label>
        <input
          type="text"
          name="name"
          value={formData.name}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Rule Name"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Description
        </label>
        <textarea
          name="description"
          value={formData.description}
          onChange={handleChange}
          rows={3}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Rule description"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Device Type (leave empty for all types)
        </label>
        <select
          name="device_type"
          value={formData.device_type}
          onChange={(e) => {
            setFormData({
              ...formData,
              device_type: e.target.value,
              device_id: '', // Reset device_id when device_type changes
            });
          }}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Device Types</option>
          {availableDeviceTypes.map((deviceType) => (
            <option key={deviceType} value={deviceType}>
              {deviceType}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1">
          Device ID (leave empty for all devices)
        </label>
        <select
          name="device_id"
          value={formData.device_id}
          onChange={handleChange}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={filteredDevices.length === 0}
        >
          <option value="">All Devices</option>
          {filteredDevices.map((device) => (
            <option key={device.device_id} value={device.device_id}>
              {device.device_id} {device.device_name ? `(${device.device_name})` : ''}
            </option>
          ))}
        </select>
        {formData.device_type && filteredDevices.length === 0 && (
          <p className="text-xs text-gray-500 mt-1">No devices found for selected device type</p>
        )}
      </div>

      <div className="border-t border-gray-700 pt-4">
        <h4 className="text-sm font-medium text-gray-300 mb-3">Condition</h4>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Condition Type <span className="text-red-400">*</span>
            </label>
            <select
              name="condition_type"
              value={formData.condition_type}
              onChange={handleChange}
              required
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="threshold">Threshold</option>
              <option value="status">Status</option>
              <option value="range">Range</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Field <span className="text-red-400">*</span>
            </label>
            {fieldsToShow.length > 0 ? (
              <select
                name="condition_field"
                value={formData.condition_field}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a field</option>
                {fieldsToShow.map((field) => (
                  <option key={field.value} value={field.value} title={field.description}>
                    {field.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                name="condition_field"
                value={formData.condition_field}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter field name (e.g., voltage, temperature)"
              />
            )}
            {formData.device_type && availableFields.length > 0 && formData.condition_field && (
              <p className="text-xs text-gray-500 mt-1">
                {availableFields.find(f => f.value === formData.condition_field)?.description || ''}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Operator <span className="text-red-400">*</span>
            </label>
            <select
              name="condition_operator"
              value={formData.condition_operator}
              onChange={handleChange}
              required
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value=">">&gt;</option>
              <option value=">=">&gt;=</option>
              <option value="<">&lt;</option>
              <option value="<=">&lt;=</option>
              <option value="==">==</option>
              <option value="!=">!=</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Value <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              name="condition_value"
              value={formData.condition_value}
              onChange={handleChange}
              required
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="0.08, 43, etc."
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Severity <span className="text-red-400">*</span>
          </label>
          <select
            name="severity"
            value={formData.severity}
            onChange={handleChange}
            required
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="Info">Info</option>
            <option value="Warning">Warning</option>
            <option value="High">High</option>
            <option value="Critical">Critical</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Priority <span className="text-red-400">*</span>
          </label>
          <input
            type="number"
            name="priority"
            value={formData.priority}
            onChange={handleChange}
            required
            min="0"
            max="10"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="5"
          />
        </div>
      </div>

      <div className="border-t border-gray-700 pt-4">
        <h4 className="text-sm font-medium text-gray-300 mb-3">Actions</h4>
        <div className="space-y-2">
          {formData.actions && formData.actions.map((action: any, index: number) => (
            <div key={action.name} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={action.enabled}
                  onChange={(e) => {
                    const newActions = [...formData.actions];
                    newActions[index] = { ...action, enabled: e.target.checked };
                    setFormData({ ...formData, actions: newActions });
                  }}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <label className="text-sm text-gray-300 capitalize">
                  {action.name.replace(/_/g, ' ')}
                </label>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Select which actions should be executed when this rule is triggered
        </p>
      </div>

      <div className="flex justify-between items-center pt-4">
        {initialRule && onDelete && (
          <Button
            type="button"
            variant="danger"
            onClick={() => {
              if (window.confirm(`Are you sure you want to delete rule "${initialRule.id}"?`)) {
                onDelete(initialRule.id);
              }
            }}
            disabled={submitting}
            className="hover:shadow-lg hover:shadow-red-500/20 transition-all duration-200"
          >
            <Trash2 size={16} className="mr-2" />
            Delete Rule
          </Button>
        )}
        {!initialRule && <div />}
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={submitting}
          >
            {submitting ? (initialRule ? 'Updating...' : 'Adding...') : (initialRule ? 'Update Rule' : 'Add Rule')}
          </Button>
        </div>
      </div>
    </form>
  );
};

