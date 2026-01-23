"""
Variable Knowledge Base for EMS System
Defines variables, their roles, relationships, and device associations
"""

from typing import Dict, List, Set, Optional

# Variable knowledge base: variable -> {role, device_types, related_variables, description}
VARIABLE_KNOWLEDGE: Dict[str, Dict[str, any]] = {
    # BMS Variables
    "soc": {
        "role": "Battery State of Charge - indicates remaining battery capacity",
        "device_types": ["BMS", "BESS", "ESS"],
        "related_variables": ["soh", "voltage", "current", "active_power"],
        "description": "State of Charge (0-100%), critical for battery health monitoring",
        "influences": ["active_power", "max_charge_power_limit", "max_discharge_power_limit"],
        "influenced_by": ["current", "active_power", "temperature"],
    },
    "soh": {
        "role": "Battery State of Health - indicates battery degradation",
        "device_types": ["BMS", "BESS", "ESS"],
        "related_variables": ["soc", "cell_voltages", "temperature", "max_delta_v"],
        "description": "State of Health (0-100%), indicates remaining battery life",
        "influences": ["max_charge_power_limit", "max_discharge_power_limit", "capacity"],
        "influenced_by": ["temperature", "charge_cycles", "cell_voltages"],
    },
    "voltage": {
        "role": "Battery voltage - indicates electrical potential",
        "device_types": ["BMS", "PCS", "UPS", "BESS", "ESS"],
        "related_variables": ["current", "active_power", "soc", "cell_voltages"],
        "description": "Battery pack voltage (V), affects power output capability",
        "influences": ["active_power", "current", "soc"],
        "influenced_by": ["current", "soc", "temperature", "cell_voltages"],
    },
    "current": {
        "role": "Battery current - indicates charge/discharge rate",
        "device_types": ["BMS", "PCS", "UPS", "BESS", "ESS"],
        "related_variables": ["voltage", "active_power", "soc", "temperature"],
        "description": "Battery current (A), positive for discharge, negative for charge",
        "influences": ["soc", "temperature", "voltage"],
        "influenced_by": ["active_power", "voltage", "max_charge_power_limit", "max_discharge_power_limit"],
    },
    "temperature": {
        "role": "Battery temperature - critical for safety and performance",
        "device_types": ["BMS", "TMS", "UPS", "HTS", "BESS", "ESS"],
        "related_variables": ["soc", "current", "voltage", "coolant_temperature", "ambient_temperature"],
        "description": "Battery temperature (°C), affects performance and safety",
        "influences": ["soc", "soh", "max_charge_power_limit", "max_discharge_power_limit", "active_power"],
        "influenced_by": ["current", "ambient_temperature", "coolant_temperature", "active_power"],
    },
    "cell_voltages": {
        "role": "Individual cell voltages - indicates cell balance",
        "device_types": ["BMS"],
        "related_variables": ["voltage", "max_voltage", "min_voltage", "max_delta_v", "soc"],
        "description": "Array of individual cell voltages (V), used for cell balancing",
        "influences": ["voltage", "max_delta_v", "soc", "soh"],
        "influenced_by": ["current", "soc", "temperature"],
    },
    "max_voltage": {
        "role": "Maximum cell voltage - indicates overcharge risk",
        "device_types": ["BMS"],
        "related_variables": ["cell_voltages", "min_voltage", "max_delta_v", "soc"],
        "description": "Maximum cell voltage (V), used for overcharge protection",
        "influences": ["max_charge_power_limit", "soc"],
        "influenced_by": ["cell_voltages", "current", "soc"],
    },
    "min_voltage": {
        "role": "Minimum cell voltage - indicates overdischarge risk",
        "device_types": ["BMS"],
        "related_variables": ["cell_voltages", "max_voltage", "max_delta_v", "soc"],
        "description": "Minimum cell voltage (V), used for overdischarge protection",
        "influences": ["max_discharge_power_limit", "soc"],
        "influenced_by": ["cell_voltages", "current", "soc"],
    },
    "max_delta_v": {
        "role": "Maximum cell voltage difference - indicates cell imbalance",
        "device_types": ["BMS"],
        "related_variables": ["cell_voltages", "max_voltage", "min_voltage", "soh"],
        "description": "Maximum voltage difference between cells (V), indicates cell imbalance",
        "influences": ["soh", "max_charge_power_limit", "max_discharge_power_limit"],
        "influenced_by": ["cell_voltages", "current", "temperature"],
    },
    
    # PCS Variables
    "active_power": {
        "role": "Active power output - indicates power flow",
        "device_types": ["PCS", "BESS", "ESS"],
        "related_variables": ["reactive_power", "voltage", "current", "soc", "efficiency"],
        "description": "Active power (kW), positive for discharge, negative for charge",
        "influences": ["soc", "current", "voltage", "temperature"],
        "influenced_by": ["voltage", "current", "soc", "max_charge_power_limit", "max_discharge_power_limit"],
    },
    "reactive_power": {
        "role": "Reactive power output - indicates power factor",
        "device_types": ["PCS", "BESS", "ESS"],
        "related_variables": ["active_power", "voltage", "current", "frequency"],
        "description": "Reactive power (kVAR), affects power factor",
        "influences": ["efficiency", "voltage"],
        "influenced_by": ["active_power", "voltage", "frequency"],
    },
    "frequency": {
        "role": "Grid frequency - indicates grid stability",
        "device_types": ["PCS", "METER"],
        "related_variables": ["voltage", "active_power", "reactive_power"],
        "description": "Grid frequency (Hz), typically 50Hz or 60Hz",
        "influences": ["active_power", "reactive_power"],
        "influenced_by": ["grid_conditions"],
    },
    "efficiency": {
        "role": "Power conversion efficiency - indicates system performance",
        "device_types": ["PCS"],
        "related_variables": ["active_power", "reactive_power", "voltage", "current", "temperature"],
        "description": "Power conversion efficiency (%), indicates system performance",
        "influences": ["active_power", "temperature"],
        "influenced_by": ["active_power", "reactive_power", "voltage", "current", "temperature"],
    },
    "max_charge_power_limit": {
        "role": "Maximum charge power limit - protects battery during charging",
        "device_types": ["PCS", "BMS", "BESS", "ESS"],
        "related_variables": ["soc", "soh", "temperature", "voltage", "max_voltage"],
        "description": "Maximum charge power limit (kW), protects battery",
        "influences": ["active_power", "current"],
        "influenced_by": ["soc", "soh", "temperature", "max_voltage", "max_delta_v"],
    },
    "max_discharge_power_limit": {
        "role": "Maximum discharge power limit - protects battery during discharging",
        "device_types": ["PCS", "BMS", "BESS", "ESS"],
        "related_variables": ["soc", "soh", "temperature", "voltage", "min_voltage"],
        "description": "Maximum discharge power limit (kW), protects battery",
        "influences": ["active_power", "current"],
        "influenced_by": ["soc", "soh", "temperature", "min_voltage", "max_delta_v"],
    },
    
    # TMS Variables
    "coolant_temperature": {
        "role": "Coolant temperature - indicates thermal management effectiveness",
        "device_types": ["TMS"],
        "related_variables": ["temperature", "ambient_temperature", "active_power"],
        "description": "Coolant temperature (°C), used for battery cooling",
        "influences": ["temperature"],
        "influenced_by": ["temperature", "active_power", "ambient_temperature"],
    },
    "ambient_temperature": {
        "role": "Ambient temperature - indicates environmental conditions",
        "device_types": ["TMS", "HTS"],
        "related_variables": ["temperature", "coolant_temperature"],
        "description": "Ambient temperature (°C), affects battery temperature",
        "influences": ["temperature", "coolant_temperature"],
        "influenced_by": ["environmental_conditions"],
    },
    
    # UPS Variables
    "input_voltage": {
        "role": "Input voltage - indicates power supply status",
        "device_types": ["UPS"],
        "related_variables": ["output_voltage", "battery_voltage", "status"],
        "description": "Input voltage (V), indicates power supply status",
        "influences": ["output_voltage", "status"],
        "influenced_by": ["grid_conditions"],
    },
    "output_voltage": {
        "role": "Output voltage - indicates load power supply",
        "device_types": ["UPS"],
        "related_variables": ["input_voltage", "battery_voltage", "status"],
        "description": "Output voltage (V), indicates load power supply",
        "influences": ["status"],
        "influenced_by": ["input_voltage", "battery_voltage"],
    },
    "battery_voltage": {
        "role": "UPS battery voltage - indicates backup power availability",
        "device_types": ["UPS"],
        "related_variables": ["input_voltage", "output_voltage", "status"],
        "description": "UPS battery voltage (V), indicates backup power availability",
        "influences": ["output_voltage", "status"],
        "influenced_by": ["input_voltage", "charge_status"],
    },
    
    # Power System Variables
    "power": {
        "role": "Generic power measurement",
        "device_types": ["METER", "BESS", "ESS"],
        "related_variables": ["active_power", "voltage", "current"],
        "description": "Generic power measurement (kW)",
        "influences": ["active_power"],
        "influenced_by": ["voltage", "current"],
    },
    "energy": {
        "role": "Energy measurement - indicates total energy flow",
        "device_types": ["METER", "BESS", "ESS"],
        "related_variables": ["active_power", "soc"],
        "description": "Energy measurement (kWh), total energy flow",
        "influences": ["soc"],
        "influenced_by": ["active_power"],
    },
}


def get_variable_info(variable_name: str) -> Optional[Dict[str, any]]:
    """Get information about a variable"""
    return VARIABLE_KNOWLEDGE.get(variable_name.lower())


def get_variables_for_device_type(device_type: str) -> List[str]:
    """Get all variables available for a device type"""
    device_type_upper = device_type.upper()
    variables = []
    for var_name, var_info in VARIABLE_KNOWLEDGE.items():
        if device_type_upper in var_info.get("device_types", []):
            variables.append(var_name)
    return variables


def get_related_variables(variable_name: str) -> List[str]:
    """Get variables related to a given variable"""
    var_info = get_variable_info(variable_name)
    if not var_info:
        return []
    
    related = set()
    # Add directly related variables
    related.update(var_info.get("related_variables", []))
    # Add variables that influence this variable
    related.update(var_info.get("influenced_by", []))
    # Add variables influenced by this variable
    related.update(var_info.get("influences", []))
    
    return list(related)


def validate_variable_exists(
    variable_name: str,
    device_id: str,
    device_type: str,
    available_variables: Set[str],
    available_devices: Dict[str, Dict[str, any]],
) -> Dict[str, any]:
    """
    Validate if a variable exists for a device
    
    Returns:
        {
            "exists": bool,
            "device_exists": bool,
            "variable_available": bool,
            "device_type_match": bool,
            "message": str
        }
    """
    var_info = get_variable_info(variable_name)
    
    # Check if device exists
    device_exists = device_id in available_devices
    device_info = available_devices.get(device_id, {})
    actual_device_type = device_info.get("device_type", "").upper()
    
    # Check if variable is available for this device
    variable_available = variable_name.lower() in available_variables
    
    # Check if device type matches
    device_type_match = False
    if var_info:
        expected_device_types = [dt.upper() for dt in var_info.get("device_types", [])]
        device_type_match = actual_device_type in expected_device_types
    
    # Build message
    if not device_exists:
        message = f"Device {device_id} does not exist"
    elif not var_info:
        message = f"Variable {variable_name} is not recognized in EMS system"
    elif not device_type_match:
        message = f"Variable {variable_name} is not available for device type {actual_device_type} (expected: {', '.join(var_info.get('device_types', []))})"
    elif not variable_available:
        message = f"Variable {variable_name} is not available in collected data for device {device_id}"
    else:
        message = f"Variable {variable_name} exists and is valid for device {device_id}"
    
    return {
        "exists": device_exists and variable_available and device_type_match and var_info is not None,
        "device_exists": device_exists,
        "variable_available": variable_available,
        "device_type_match": device_type_match,
        "variable_recognized": var_info is not None,
        "message": message,
        "variable_info": var_info,
    }

