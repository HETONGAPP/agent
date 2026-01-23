"""
BMS (Battery Management System) Integration
Contains all BMS-related content: data models, collector, configuration, etc.
"""

from ...core.integration import IntegrationConfig
from ...core.integration_registry import register_integration
from ...models.device_data import DeviceType
from .collector import BMSCollector, BMSIntegration
from .models import BMSData


# Auto-register BMS integration
def _create_bms_integration(config: IntegrationConfig):
    return BMSIntegration(config)


register_integration(DeviceType.BMS, "bms", _create_bms_integration)

__all__ = ["BMSData", "BMSCollector", "BMSIntegration"]
