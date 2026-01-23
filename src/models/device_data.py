"""
Generic device data model for all energy storage system components
Supports BMS, PCS, UPS, TMS, and other components
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class DeviceType(str, Enum):
    """Device type enumeration - Universal support for all energy storage system components"""

    # Core Energy Storage Components
    BMS = "BMS"  # Battery Management System
    PCS = "PCS"  # Power Conversion System (includes Storage/PV/Generic inverters)
    UPS = "UPS"  # Uninterruptible Power Supply
    TMS = "TMS"  # Thermal Management System
    EMS = "EMS"  # Energy Management System
    
    # Power System Components
    METER = "METER"  # Power Meter
    TRANSFORMER = "TRANSFORMER"  # Transformer
    GSB = "GSB"  # Grid Service Breaker
    SPPC = "SPPC"  # Smart Power Point Controller
    
    # Charging and Load Management
    EVCS = "EVCS"  # Electric Vehicle Charging Station
    
    # Environmental Control
    FAN = "FAN"  # Fan/Cooling Fan
    HVAC = "HVAC"  # Heating, Ventilation, and Air Conditioning
    
    # Monitoring and Sensors
    HTS = "HTS"  # Humidity/Temperature Sensor
    
    # Safety and Backup
    FMS = "FMS"  # Fire Management System
    GENSET = "GENSET"  # Generator Set
    
    # Data and Communication
    DATALOGGER = "DATALOGGER"  # Data Logger
    MONITORING = "MONITORING"  # Monitoring System
    
    # Aggregation
    BESS = "BESS"  # Battery Energy Storage System (aggregated)
    ESS = "ESS"  # Energy Storage System (aggregated)
    
    # Other
    OTHER = "OTHER"  # Other components


@dataclass
class DeviceData:
    """
    Generic device data model
    Flexible structure to support all energy storage system components
    Supports multi-site scenarios
    """

    device_id: str
    device_type: DeviceType
    timestamp: datetime
    source: str  # Data source identifier
    site_id: Optional[str] = None  # Site ID for multi-site support
    site_name: Optional[str] = None  # Site name for multi-site support
    data: Dict[str, Any] = field(default_factory=dict)  # Flexible data container
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def get_field(self, field_path: str, default: Any = None) -> Any:
        """
        Get field value using dot notation path
        Example: get_field('voltage.max') or get_field('temperature')
        """
        keys = field_path.split(".")
        value = self.data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def has_field(self, field_path: str) -> bool:
        """Check if field exists"""
        return self.get_field(field_path) is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
        }
        if self.site_id:
            result["site_id"] = self.site_id
        if self.site_name:
            result["site_name"] = self.site_name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceData":
        """Create from dictionary with validation"""
        from datetime import UTC
        
        # Validate required fields
        if "device_id" not in data:
            raise ValueError("device_id is required")
        if "source" not in data:
            raise ValueError("source is required")
        
        # Parse timestamp with error handling
        timestamp = data.get("timestamp")
        if timestamp is None:
            timestamp = datetime.now(UTC)
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                # Fallback to current time if parsing fails
                timestamp = datetime.now(UTC)
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = datetime.now(UTC)
        
        # Validate device_type
        device_type_str = data.get("device_type", "OTHER")
        try:
            device_type = DeviceType(device_type_str.upper())
        except ValueError:
            device_type = DeviceType.OTHER
        
        return cls(
            device_id=data["device_id"],
            device_type=device_type,
            timestamp=timestamp,
            source=data["source"],
            site_id=data.get("site_id"),
            site_name=data.get("site_name"),
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_bms_data(cls, bms_data, device_id: str, source: str) -> "DeviceData":
        """
        Create DeviceData from BMSData (for backward compatibility)

        Args:
            bms_data: BMSData object (from integrations.bms)
            device_id: Device ID
            source: Data source
        """

        return cls(
            device_id=device_id,
            device_type=DeviceType.BMS,
            timestamp=bms_data.timestamp,
            source=source,
            data={
                "cell_voltages": bms_data.cell_voltages,
                "temperatures": bms_data.temperatures,
                "soc": bms_data.soc,
                "soh": bms_data.soh,
                "max_delta_v": bms_data.max_delta_v,
                "pack_id": bms_data.pack_id,
                "max_voltage": bms_data.max_voltage,
                "min_voltage": bms_data.min_voltage,
                "max_temperature": bms_data.max_temperature,
                "min_temperature": bms_data.min_temperature,
            },
            metadata={"pack_id": bms_data.pack_id},
        )


@dataclass
class PCSData:
    """PCS (Power Conversion System) data model"""

    device_id: str
    timestamp: datetime
    active_power: float  # kW
    reactive_power: float  # kVAR
    voltage: float  # V
    current: float  # A
    frequency: float  # Hz
    efficiency: float  # %
    status: str  # running, stopped, fault, etc.
    temperature: Optional[float] = None  # °C
    grid_connection_status: Optional[str] = None  # connected, disconnected
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_device_data(self, source: str) -> DeviceData:
        """Convert to DeviceData"""
        return DeviceData(
            device_id=self.device_id,
            device_type=DeviceType.PCS,
            timestamp=self.timestamp,
            source=source,
            data={
                "active_power": self.active_power,
                "reactive_power": self.reactive_power,
                "voltage": self.voltage,
                "current": self.current,
                "frequency": self.frequency,
                "efficiency": self.efficiency,
                "status": self.status,
                "temperature": self.temperature,
                "grid_connection_status": self.grid_connection_status,
            },
            metadata=self.metadata,
        )


@dataclass
class UPSData:
    """UPS (Uninterruptible Power Supply) data model"""

    device_id: str
    timestamp: datetime
    input_voltage: float  # V
    output_voltage: float  # V
    battery_voltage: float  # V
    load_percentage: float  # %
    battery_capacity: float  # %
    status: str  # normal, battery, bypass, fault
    temperature: Optional[float] = None  # °C
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_device_data(self, source: str) -> DeviceData:
        """Convert to DeviceData"""
        return DeviceData(
            device_id=self.device_id,
            device_type=DeviceType.UPS,
            timestamp=self.timestamp,
            source=source,
            data={
                "input_voltage": self.input_voltage,
                "output_voltage": self.output_voltage,
                "battery_voltage": self.battery_voltage,
                "load_percentage": self.load_percentage,
                "battery_capacity": self.battery_capacity,
                "status": self.status,
                "temperature": self.temperature,
            },
            metadata=self.metadata,
        )


@dataclass
class TMSData:
    """TMS (Thermal Management System) data model"""

    device_id: str
    timestamp: datetime
    ambient_temperature: float  # °C
    coolant_temperature: float  # °C
    coolant_flow_rate: float  # L/min
    cooling_system_status: str  # running, stopped, fault
    fan_speed: Optional[float] = None  # RPM
    pump_status: Optional[str] = None  # running, stopped, fault
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_device_data(self, source: str) -> DeviceData:
        """Convert to DeviceData"""
        return DeviceData(
            device_id=self.device_id,
            device_type=DeviceType.TMS,
            timestamp=self.timestamp,
            source=source,
            data={
                "ambient_temperature": self.ambient_temperature,
                "coolant_temperature": self.coolant_temperature,
                "coolant_flow_rate": self.coolant_flow_rate,
                "fan_speed": self.fan_speed,
                "cooling_system_status": self.cooling_system_status,
                "pump_status": self.pump_status,
            },
            metadata=self.metadata,
        )
