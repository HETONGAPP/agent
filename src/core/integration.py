"""
Device integration interface definitions
Core system only depends on these interfaces, not on specific implementations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..models.alarm import Alarm
from ..models.device_data import DeviceData, DeviceType


@dataclass
class IntegrationConfig:
    """Base class for integration configuration"""

    enabled: bool = True
    device_type: DeviceType = DeviceType.OTHER
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    interval: int = 30
    timeout: int = 10
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DeviceIntegration(ABC):
    """
    Device integration interface
    All device integrations (BMS, PCS, etc.) must implement this interface
    """

    def __init__(self, config: IntegrationConfig):
        """
        Initialize integration

        Args:
            config: Integration configuration
        """
        self.config = config
        self.device_type = config.device_type

    @abstractmethod
    async def collect_alarms(self) -> List[Alarm]:
        """
        Collect alarm data

        Returns:
            List of alarms
        """
        pass

    @abstractmethod
    async def get_device_data(self, device_id: str) -> DeviceData:
        """
        Get device data

        Args:
            device_id: Device ID

        Returns:
            Device data object
        """
        pass

    @abstractmethod
    async def get_context_data(self, alarm_id: str) -> Dict[str, Any]:
        """
        Get alarm context data

        Args:
            alarm_id: Alarm ID

        Returns:
            Context data dictionary
        """
        pass

    def get_device_type(self) -> DeviceType:
        """
        Get device type

        Returns:
            Device type
        """
        return self.device_type

    def is_enabled(self) -> bool:
        """
        Check if integration is enabled

        Returns:
            Whether integration is enabled
        """
        return self.config.enabled

    @abstractmethod
    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover available devices for this integration

        Returns:
            List of device information dictionaries with keys:
            - device_id: Device ID
            - device_type: Device type
            - metadata: Optional device metadata
        """
        pass

    def get_integration_name(self) -> str:
        """
        Get integration name (e.g., "bms", "pcs")

        Returns:
            Integration name
        """
        return self.device_type.value.lower()
