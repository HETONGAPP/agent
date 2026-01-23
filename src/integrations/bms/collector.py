"""
BMS data collector
"""

import logging
from typing import Any, Dict, List

from ...core.integration import DeviceIntegration, IntegrationConfig
from ...models.alarm import Alarm
from ...models.device_data import DeviceData
from .models import BMSData

logger = logging.getLogger(__name__)


class BMSCollector:
    """BMS data collector"""

    def __init__(self, api_url: str, api_key: str):
        """
        Initialize BMS collector

        Args:
            api_url: BMS API URL
            api_key: API key
        """
        self.api_url = api_url
        self.api_key = api_key

    async def collect_alarms(self) -> List[Alarm]:
        """
        Collect alarm data from BMS API

        Returns:
            List of Alarm objects

        TODO: Implement real API calls when BMS_API_URL is configured
        """
        # If API URL is configured, this should make real API calls
        if self.api_url and self.api_url.strip():
            # TODO: Implement real BMS API calls
            raise NotImplementedError("BMS API integration pending - real API calls not yet implemented")
        
        # Return empty list for now (no mock alarms)
        # In production, this should query the actual BMS API
        return []

    async def get_context_data(self, alarm_id: str) -> Dict[str, Any]:
        """
        Get alarm context data

        Args:
            alarm_id: Alarm ID

        Returns:
            Context data dictionary

        TODO: Implement real API calls when BMS_API_URL is configured
        """
        # If API URL is configured, this should make real API calls
        if self.api_url and self.api_url.strip():
            # TODO: Implement real BMS API calls
            raise NotImplementedError("BMS API integration pending - real API calls not yet implemented")
        
        # Return empty context for now
        # In production, this should query the actual BMS API for alarm context
        return {
            "alarm_id": alarm_id,
            "context": "No context data available (device data received via MQTT)",
        }

    async def get_bms_data(self, pack_id: str) -> BMSData:
        """
        Get BMS data from API (if configured)
        
        NOTE: This method is only used when BMS_API_URL is configured.
        In normal operation, device data is received via MQTT, not through this method.
        
        Args:
            pack_id: Battery pack ID or device ID

        Returns:
            BMSData object
            
        Raises:
            NotImplementedError: If BMS_API_URL is not configured or real API calls are not implemented
        """
        # Device data should be received via MQTT, not through this method
        # This method is only for future API integration when BMS_API_URL is configured
        if not self.api_url or not self.api_url.strip():
            raise NotImplementedError(
                f"BMS data collection via API not configured. "
                f"Device data should be received via MQTT for device {pack_id}."
            )
        
        # TODO: Implement real BMS API calls when BMS_API_URL is configured
        raise NotImplementedError(
            f"BMS API integration pending - real API calls not yet implemented for {pack_id}. "
            f"Device data should be received via MQTT."
        )


class BMSIntegration(DeviceIntegration):
    """BMS integration implementation"""

    def __init__(self, config: IntegrationConfig):
        """
        Initialize BMS integration

        Args:
            config: BMS integration configuration
        """
        super().__init__(config)
        self.collector = BMSCollector(
            api_url=config.api_url or "", api_key=config.api_key or ""
        )

    async def collect_alarms(self) -> List[Alarm]:
        """Collect BMS alarms"""
        return await self.collector.collect_alarms()

    async def get_device_data(self, device_id: str) -> DeviceData:
        """
        Get BMS device data
        
        NOTE: This method is deprecated. Device data should be received via MQTT.
        This method is kept for backward compatibility but will raise an error.

        Args:
            device_id: Device ID

        Returns:
            Device data object
            
        Raises:
            NotImplementedError: Device data should be received via MQTT
        """
        # Device data should be received via MQTT, not through this method
        raise NotImplementedError(
            f"Device data for {device_id} should be received via MQTT, not through API. "
            f"Please ensure MQTT broker is configured and device is sending data to MQTT topics."
        )

    async def get_context_data(self, alarm_id: str) -> Dict[str, Any]:
        """Get alarm context data"""
        return await self.collector.get_context_data(alarm_id)

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover available BMS devices

        Returns:
            List of device information dictionaries
            
        NOTE: Device registration is now manual-only (frontend-initiated).
        This method is kept for future use when real BMS API integration is implemented.
        Currently returns empty list as devices must be manually registered via frontend.
        """
        # Device registration is now manual-only (frontend-initiated)
        # No automatic device discovery - all devices must be registered via frontend
        # This method is kept for future use when real BMS API integration is implemented
        
        # TODO: When BMS_API_URL is configured, implement real device discovery:
        # if self.config.api_url and self.config.api_url.strip():
        #     devices = await self.collector.discover_bms_devices()
        #     return [
        #         {
        #             "device_id": device["id"],
        #             "device_type": DeviceType.BMS.value,
        #             "metadata": device.get("metadata", {})
        #         }
        #         for device in devices
        #     ]
        
        # Return empty list - devices must be manually registered
        return []
