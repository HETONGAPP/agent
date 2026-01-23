"""
Core module - defines system core interfaces
"""

from .data_collection_service import DataCollectionService
from .device_discovery import DeviceDiscoveryService
from .device_registry import DeviceRegistry, DeviceStatus, RegisteredDevice
from .integration import DeviceIntegration, IntegrationConfig
from .integration_factory import IntegrationFactory
from .integration_manager import IntegrationManager
from .integration_registry import (
    IntegrationRegistry,
    get_integration_registry,
    register_integration,
)

__all__ = [
    "DeviceIntegration",
    "IntegrationConfig",
    "IntegrationFactory",
    "DeviceRegistry",
    "RegisteredDevice",
    "DeviceStatus",
    "IntegrationRegistry",
    "get_integration_registry",
    "register_integration",
    "DeviceDiscoveryService",
    "IntegrationManager",
    "DataCollectionService",
]
