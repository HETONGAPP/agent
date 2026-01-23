"""
PCS data model
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ...models.device_data import DeviceData, DeviceType


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
