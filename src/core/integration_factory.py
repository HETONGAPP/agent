"""
Integration factory - for creating and managing device integrations
"""

from typing import Dict, Optional

from ..models.device_data import DeviceType
from .integration import DeviceIntegration, IntegrationConfig
from .integration_registry import get_integration_registry


class IntegrationFactory:
    """Integration factory class"""

    @staticmethod
    def create_integration(
        device_type: DeviceType, config: IntegrationConfig
    ) -> Optional[DeviceIntegration]:
        """
        Create integration instance based on device type

        Args:
            device_type: Device type
            config: Integration configuration

        Returns:
            Integration instance, or None if device type is not supported
        """
        if not config.enabled:
            return None

        # Try to get factory from registry first
        registry = get_integration_registry()
        if registry.is_registered(device_type):
            return registry.create_integration(device_type, config)

        # Fallback to direct imports (for backward compatibility)
        if device_type == DeviceType.BMS:
            from ..integrations.bms import BMSIntegration

            integration = BMSIntegration(config)
            # Register in registry for future use
            registry.register_integration(
                DeviceType.BMS, "bms", lambda cfg: BMSIntegration(cfg)
            )
            return integration
        elif device_type == DeviceType.PCS:
            from ..integrations.pcs import PCSIntegration

            integration = PCSIntegration(config)
            # Register in registry for future use
            registry.register_integration(
                DeviceType.PCS, "pcs", lambda cfg: PCSIntegration(cfg)
            )
            return integration
        # Add more device type integrations here
        else:
            return None

    @staticmethod
    def create_integrations_from_config(
        config_dict: Dict[str, Dict],
    ) -> Dict[DeviceType, DeviceIntegration]:
        """
        Create all integrations from configuration dictionary

        Args:
            config_dict: Configuration dictionary, format:
                {
                    "bms": {
                        "enabled": True,
                        "api_url": "...",
                        "api_key": "...",
                        ...
                    },
                    "pcs": {...}
                }

        Returns:
            Dictionary mapping device types to integration instances
        """
        integrations = {}

        # BMS integration
        if "bms" in config_dict:
            bms_config = config_dict["bms"]
            integration_config = IntegrationConfig(
                enabled=bms_config.get("enabled", True),
                device_type=DeviceType.BMS,
                api_url=bms_config.get("api_url"),
                api_key=bms_config.get("api_key"),
                interval=bms_config.get("interval", 30),
                timeout=bms_config.get("timeout", 10),
                metadata=bms_config.get("metadata", {}),
            )
            integration = IntegrationFactory.create_integration(
                DeviceType.BMS, integration_config
            )
            if integration:
                integrations[DeviceType.BMS] = integration

        # PCS integration
        if "pcs" in config_dict:
            pcs_config = config_dict["pcs"]
            integration_config = IntegrationConfig(
                enabled=pcs_config.get("enabled", True),
                device_type=DeviceType.PCS,
                api_url=pcs_config.get("api_url"),
                api_key=pcs_config.get("api_key"),
                interval=pcs_config.get("interval", 30),
                timeout=pcs_config.get("timeout", 10),
                metadata=pcs_config.get("metadata", {}),
            )
            integration = IntegrationFactory.create_integration(
                DeviceType.PCS, integration_config
            )
            if integration:
                integrations[DeviceType.PCS] = integration

        return integrations
