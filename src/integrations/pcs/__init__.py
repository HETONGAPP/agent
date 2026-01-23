"""
PCS (Power Conversion System) Integration
Contains all PCS-related content: data models, collector, configuration, etc.
"""

from ...core.integration import IntegrationConfig
from ...core.integration_registry import register_integration
from ...models.device_data import DeviceType
from .collector import PCSCollector, PCSIntegration
from .models import PCSData


# Auto-register PCS integration
def _create_pcs_integration(config: IntegrationConfig):
    return PCSIntegration(config)


register_integration(DeviceType.PCS, "pcs", _create_pcs_integration)

__all__ = ["PCSData", "PCSCollector", "PCSIntegration"]
