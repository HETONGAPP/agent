"""
BMS data model
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ...models.device_data import DeviceData


@dataclass
class BMSData:
    """BMS data model"""

    timestamp: datetime
    cell_voltages: List[float]  # List of cell voltages
    temperatures: List[float]  # List of temperatures
    soc: float  # State of Charge (0-100)
    soh: float  # State of Health (0-100)
    max_delta_v: float  # Maximum voltage difference
    pack_id: str  # Battery pack ID

    @property
    def max_voltage(self) -> float:
        """Maximum voltage"""
        return max(self.cell_voltages) if self.cell_voltages else 0.0

    @property
    def min_voltage(self) -> float:
        """Minimum voltage"""
        return min(self.cell_voltages) if self.cell_voltages else 0.0

    @property
    def max_temperature(self) -> float:
        """Maximum temperature"""
        return max(self.temperatures) if self.temperatures else 0.0

    @property
    def min_temperature(self) -> float:
        """Minimum temperature"""
        return min(self.temperatures) if self.temperatures else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cell_voltages": self.cell_voltages,
            "temperatures": self.temperatures,
            "soc": self.soc,
            "soh": self.soh,
            "max_delta_v": self.max_delta_v,
            "pack_id": self.pack_id,
            "max_voltage": self.max_voltage,
            "min_voltage": self.min_voltage,
            "max_temperature": self.max_temperature,
            "min_temperature": self.min_temperature,
        }

    @classmethod
    def from_device_data(cls, device_data: "DeviceData") -> "BMSData":
        """
        Create BMSData from DeviceData

        Args:
            device_data: DeviceData object with BMS data

        Returns:
            BMSData object
        """

        data = device_data.data

        # Extract pack_id from data or metadata
        pack_id = data.get("pack_id") or device_data.metadata.get(
            "pack_id", f"PACK_{device_data.device_id}"
        )

        # Extract required fields
        cell_voltages = data.get("cell_voltages", [])
        temperatures = data.get("temperatures", [])
        soc = data.get("soc", 0.0)
        soh = data.get("soh", 100.0)
        max_delta_v = data.get("max_delta_v", 0.0)

        # If max_delta_v not provided, calculate from cell_voltages
        if not max_delta_v and cell_voltages:
            max_delta_v = max(cell_voltages) - min(cell_voltages)

        return cls(
            timestamp=device_data.timestamp,
            cell_voltages=cell_voltages if isinstance(cell_voltages, list) else [],
            temperatures=temperatures if isinstance(temperatures, list) else [],
            soc=float(soc) if soc is not None else 0.0,
            soh=float(soh) if soh is not None else 100.0,
            max_delta_v=float(max_delta_v) if max_delta_v is not None else 0.0,
            pack_id=pack_id,
        )
