"""
Integration Registry
Manages available integrations and their factories
"""

from typing import Callable, Dict, Optional

from ..models.device_data import DeviceType
from .integration import DeviceIntegration, IntegrationConfig


class IntegrationRegistry:
    """Registry for managing integration factories"""

    def __init__(self):
        """Initialize integration registry"""
        self._factories: Dict[
            DeviceType, Callable[[IntegrationConfig], DeviceIntegration]
        ] = {}
        self._integration_names: Dict[
            DeviceType, str
        ] = {}  # device_type -> integration_name

    def register_integration(
        self,
        device_type: DeviceType,
        integration_name: str,
        factory: Callable[[IntegrationConfig], DeviceIntegration],
    ):
        """
        Register an integration factory

        Args:
            device_type: Device type
            integration_name: Integration name (e.g., "bms", "pcs")
            factory: Factory function that creates integration from config
        """
        self._factories[device_type] = factory
        self._integration_names[device_type] = integration_name

    def get_integration_name(self, device_type: DeviceType) -> Optional[str]:
        """Get integration name for device type"""
        return self._integration_names.get(device_type)

    def create_integration(
        self, device_type: DeviceType, config: IntegrationConfig
    ) -> Optional[DeviceIntegration]:
        """
        Create integration instance

        Args:
            device_type: Device type
            config: Integration configuration

        Returns:
            Integration instance or None
        """
        factory = self._factories.get(device_type)
        if factory and config.enabled:
            return factory(config)
        return None

    def is_registered(self, device_type: DeviceType) -> bool:
        """Check if integration is registered for device type"""
        return device_type in self._factories

    def get_registered_types(self) -> list[DeviceType]:
        """Get all registered device types"""
        return list(self._factories.keys())


# Global integration registry instance
_integration_registry = IntegrationRegistry()


def get_integration_registry() -> IntegrationRegistry:
    """Get global integration registry instance"""
    return _integration_registry


def register_integration(
    device_type: DeviceType,
    integration_name: str,
    factory: Callable[[IntegrationConfig], DeviceIntegration],
):
    """
    Register an integration (convenience function)

    Args:
        device_type: Device type
        integration_name: Integration name
        factory: Factory function
    """
    _integration_registry.register_integration(device_type, integration_name, factory)
