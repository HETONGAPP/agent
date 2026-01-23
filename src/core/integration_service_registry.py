"""
Integration Service Registry
Core tracks all available integration services here
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from ..models.device_data import DeviceType
from .integration_service_client import IntegrationServiceClient, IntegrationServiceInfo

logger = logging.getLogger(__name__)


class IntegrationServiceRegistry:
    """
    Registry for managing integration services
    Each integration runs as an independent service/app
    Core discovers and tracks them here
    """

    def __init__(self):
        """Initialize integration service registry"""
        self._services: Dict[str, IntegrationServiceClient] = {}
        self._service_health_check_interval: float = (
            10.0  # Check health every 10 seconds (faster response)
        )

    def register_service(
        self,
        service_id: str,
        device_type: DeviceType,
        service_url: str,
        service_name: str,
        version: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> IntegrationServiceClient:
        """
        Register a new integration service

        Args:
            service_id: Unique service identifier
            device_type: Device type this service handles
            service_url: Base URL of the service (e.g., "http://localhost:8001")
            service_name: Integration name (e.g., "bms")
            version: Service version (optional)
            metadata: Additional metadata (optional)

        Returns:
            IntegrationServiceClient instance
        """
        if service_id in self._services:
            logger.debug(
                f"⚠ Service {service_id} already registered. Updating registration."
            )
            # Close old client's session before replacing
            old_client = self._services[service_id]
            # Close the old client's session to prevent resource leaks
            # This is safe because we're about to replace it with a new client
            import asyncio

            try:
                # Try to get the event loop and schedule close in background (non-blocking)
                asyncio.get_running_loop()
                asyncio.create_task(old_client.close())
            except RuntimeError:
                # No running event loop, will be closed in stop()
                pass

        service_info = IntegrationServiceInfo(
            service_id=service_id,
            device_type=device_type,
            service_url=service_url,
            service_name=service_name,
            version=version,
            metadata=metadata or {},
            last_seen=datetime.now(UTC),
            is_healthy=False,
        )

        client = IntegrationServiceClient(service_info)
        self._services[service_id] = client

        logger.debug(
            f"Registered integration service: {service_id} "
            f"(type={device_type.value}, url={service_url})"
        )

        return client

    def unregister_service(self, service_id: str):
        """
        Unregister an integration service

        Args:
            service_id: Service identifier
        """
        if service_id in self._services:
            _ = self._services.pop(service_id)
            # Close client connection
            # Note: In production, you might want to await this properly
            logger.info(f"Unregistered integration service: {service_id}")

    def get_service(self, service_id: str) -> Optional[IntegrationServiceClient]:
        """
        Get service client by ID

        Args:
            service_id: Service identifier

        Returns:
            IntegrationServiceClient or None
        """
        return self._services.get(service_id)

    def get_services_by_type(
        self, device_type: DeviceType
    ) -> List[IntegrationServiceClient]:
        """
        Get all services for a device type

        Args:
            device_type: Device type

        Returns:
            List of IntegrationServiceClient instances
        """
        return [
            client
            for client in self._services.values()
            if client.service_info.device_type == device_type
        ]

    def get_all_services(self) -> List[IntegrationServiceClient]:
        """
        Get all registered services

        Returns:
            List of all IntegrationServiceClient instances
        """
        return list(self._services.values())

    def get_healthy_services(self) -> List[IntegrationServiceClient]:
        """
        Get all healthy services

        Returns:
            List of healthy IntegrationServiceClient instances
        """
        return [
            client
            for client in self._services.values()
            if client.service_info.is_healthy
        ]

    async def check_all_services_health(self):
        """Check health of all registered services"""
        for service_id, client in self._services.items():
            try:
                await client.health_check()
            except Exception:
                # Health check errors are already handled in health_check() method
                # (connection errors are logged as debug, others as warning)
                # Just continue to next service
                pass

    async def discover_devices_from_all_services(self) -> List[Dict[str, Any]]:
        """
        Discover devices from all healthy services

        Returns:
            List of device information dictionaries from all services
        """
        all_devices = []
        healthy_services = self.get_healthy_services()

        for client in healthy_services:
            try:
                devices = await client.discover_devices()
                # Add service_id to each device info
                for device in devices:
                    device["service_id"] = client.service_info.service_id
                    device["integration_name"] = client.service_info.service_name
                all_devices.extend(devices)
            except Exception as e:
                logger.error(
                    f"Error discovering devices from service "
                    f"{client.service_info.service_id}: {e}",
                    exc_info=True,
                )

        return all_devices
