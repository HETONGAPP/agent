"""
Integration Manager
Manages integrations and automatically discovers devices
Supports both direct integrations and integration services (independent apps)
"""

import asyncio
import logging
from typing import Dict, Optional

from ..models.device_data import DeviceType
from .device_discovery import DeviceDiscoveryService
from .device_registry import DeviceRegistry, DeviceStatus
from .integration import DeviceIntegration
from .integration_service_client import IntegrationServiceClient
from .integration_service_registry import IntegrationServiceRegistry

logger = logging.getLogger(__name__)


class IntegrationManager:
    """Manages integrations and device discovery"""

    def __init__(
        self,
        device_registry: Optional[DeviceRegistry] = None,
        discovery_service: Optional[DeviceDiscoveryService] = None,
        integration_discovery_interval: float = 30.0,
        use_service_mode: bool = True,
    ):
        """
        Initialize integration manager

        Args:
            device_registry: Device registry instance
            discovery_service: Device discovery service instance
            integration_discovery_interval: Interval for polling integrations for new devices (seconds)
            use_service_mode: If True, discover integration services (independent apps).
                              If False, use direct integration instances.
        """
        self.device_registry = device_registry or DeviceRegistry()
        self.discovery_service = discovery_service or DeviceDiscoveryService(
            device_registry=self.device_registry
        )
        self.integration_discovery_interval = integration_discovery_interval
        self.use_service_mode = use_service_mode

        # Direct integrations (legacy mode)
        self._integrations: Dict[DeviceType, DeviceIntegration] = {}

        # Integration services (service mode - independent apps)
        self.service_registry = (
            IntegrationServiceRegistry() if use_service_mode else None
        )

        self._running = False
        self._discovery_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the integration manager"""
        if self._running:
            logger.warning("Integration manager is already running")
            return

        self._running = True

        # Start device discovery service
        await self.discovery_service.start()

        # Start integration discovery loop
        self._discovery_task = asyncio.create_task(self._integration_discovery_loop())

        # Start health check loop for service mode
        if self.use_service_mode and self.service_registry:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.debug(
            f"Integration manager started (mode={'service' if self.use_service_mode else 'direct'})"
        )

    async def stop(self):
        """Stop the integration manager"""
        if not self._running:
            return

        self._running = False

        # Stop discovery task
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass

        # Stop health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all service clients
        if self.service_registry:
            for client in self.service_registry.get_all_services():
                await client.close()

        # Stop discovery service
        await self.discovery_service.stop()

        logger.debug("Integration manager stopped")

    async def _integration_discovery_loop(self):
        """Loop that polls integrations for new devices"""
        while self._running:
            try:
                await self._discover_devices_from_integrations()
                await asyncio.sleep(self.integration_discovery_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in integration discovery loop: {e}", exc_info=True)
                await asyncio.sleep(self.integration_discovery_interval)

    async def _discover_devices_from_integrations(self):
        """Poll all integrations to discover new devices"""
        if self.use_service_mode and self.service_registry:
            # Service mode: Poll integration services (independent apps)
            await self._discover_devices_from_services()
        else:
            # Direct mode: Poll direct integration instances
            await self._discover_devices_from_direct_integrations()

    async def _discover_devices_from_services(self):
        """Discover devices from integration services"""
        try:
            # Check health of all services first
            await self.service_registry.check_all_services_health()

            # Discover devices from all healthy services
            devices = await self.service_registry.discover_devices_from_all_services()

            for device_info in devices:
                device_id = device_info.get("device_id")
                if not device_id:
                    continue

                integration_name = device_info.get("integration_name", "unknown")
                service_id = device_info.get("service_id", "unknown")

                # Get device_type from device_info
                device_type_from_info = device_info.get("device_type")
                if device_type_from_info:
                    if isinstance(device_type_from_info, str):
                        try:
                            device_type_from_info = DeviceType(
                                device_type_from_info.upper()
                            )
                        except ValueError:
                            logger.warning(
                                f"Invalid device_type '{device_type_from_info}' "
                                f"from service {service_id}"
                            )
                            continue
                else:
                    logger.warning(
                        f"Device {device_id} from service {service_id} has no device_type"
                    )
                    continue

                # Register device if not already registered
                # Note: Frontend-initiated registration takes priority
                # Only auto-register if device doesn't exist and auto-discovery is enabled
                existing_device = self.device_registry.get_device(device_id)
                if not existing_device:
                    # Check if device was deleted (exists=False in InfluxDB)
                    # Skip auto-registration for deleted devices
                    if hasattr(self.device_registry, '_influx_storage') and self.device_registry._influx_storage:
                        deleted_device = self.device_registry._influx_storage.get_device(device_id)
                        if deleted_device is None:
                            # Device was deleted (exists=False), skip auto-registration
                            logger.debug(f"Skipping auto-discovery for deleted device: {device_id}")
                            continue
                    
                    # Check if device was manually registered via frontend (has source metadata)
                    # If auto-discovery is disabled or device has manual registration flag, skip
                    metadata = device_info.get("metadata", {})
                    if metadata.get("source") == "manual" or metadata.get("registered_via") == "frontend":
                        # Device was manually registered, skip auto-discovery
                        logger.debug(f"Skipping auto-discovery for manually registered device: {device_id}")
                        continue
                    
                    # Auto-register from service discovery
                    self.discovery_service.discover_device(
                        device_id=device_id,
                        device_type=device_type_from_info,
                        integration_name=integration_name,
                        metadata={
                            **metadata,
                            "service_id": service_id,
                            "source": "auto_discovery",
                        },
                    )
                else:
                    # Update last seen for existing device
                    self.device_registry.mark_device_seen(device_id)

        except Exception as e:
            logger.error(
                f"Error discovering devices from integration services: {e}",
                exc_info=True,
            )

    async def _discover_devices_from_direct_integrations(self):
        """Discover devices from direct integration instances (legacy mode)"""
        for device_type, integration in self._integrations.items():
            try:
                # Call integration's discover_devices method
                devices = await integration.discover_devices()

                for device_info in devices:
                    device_id = device_info.get("device_id")
                    if not device_id:
                        continue

                    integration_name = integration.get_integration_name()

                    # Get device_type from device_info or use integration's device_type
                    device_type_from_info = device_info.get("device_type")
                    if device_type_from_info:
                        # Convert string to DeviceType if needed
                        if isinstance(device_type_from_info, str):
                            try:
                                device_type_from_info = DeviceType(
                                    device_type_from_info.upper()
                                )
                            except ValueError:
                                device_type_from_info = device_type
                    else:
                        device_type_from_info = device_type

                    # Register device if not already registered
                    existing_device = self.device_registry.get_device(device_id)
                    if not existing_device:
                        # Check if device was deleted (exists=False in InfluxDB)
                        # Skip auto-registration for deleted devices
                        if hasattr(self.device_registry, '_influx_storage') and self.device_registry._influx_storage:
                            deleted_device = self.device_registry._influx_storage.get_device(device_id)
                            if deleted_device is None:
                                # Device was deleted (exists=False), skip auto-registration
                                logger.debug(f"Skipping auto-discovery for deleted device: {device_id}")
                                continue
                        
                        # Mark as auto-discovered (not manual registration)
                        auto_metadata = device_info.get("metadata", {}).copy()
                        auto_metadata["source"] = "auto-discovery"
                        auto_metadata["registered_via"] = "integration_service"
                        
                        self.discovery_service.discover_device(
                            device_id=device_id,
                            device_type=device_type_from_info,
                            integration_name=integration_name,
                            metadata=auto_metadata,
                        )
                    else:
                        # Update last seen
                        self.device_registry.mark_device_seen(device_id)

            except Exception as e:
                logger.error(
                    f"Error discovering devices from {device_type.value} integration: {e}",
                    exc_info=True,
                )

    async def _health_check_loop(self):
        """Periodically check health of all integration services"""
        while self._running:
            try:
                if self.service_registry:
                    # Track previous health status to detect changes
                    all_services = self.service_registry.get_all_services()
                    previous_health_status = {
                        client.service_info.service_id: client.service_info.is_healthy
                        for client in all_services
                    }
                    
                    # Check health of all services
                    await self.service_registry.check_all_services_health()
                    
                    # Check for health status changes and update device status accordingly
                    for client in all_services:
                        service_id = client.service_info.service_id
                        was_healthy = previous_health_status.get(service_id, True)
                        is_healthy = client.service_info.is_healthy
                        device_type = client.service_info.device_type
                        devices = self.device_registry.get_devices_by_type(device_type)
                        
                        if was_healthy and not is_healthy:
                            # Service just became unhealthy, mark all its devices as inactive
                            for device in devices:
                                if device.status == DeviceStatus.ACTIVE:
                                    device.mark_inactive()
                                    logger.warning(
                                        f"Device {device.device_id} marked as INACTIVE "
                                        f"because service {service_id} became unhealthy"
                                    )
                                    # Broadcast device status change via WebSocket
                                    await self._broadcast_device_status_change(device)
                        elif not was_healthy and is_healthy:
                            # Service just became healthy, mark inactive devices as active
                            # (they will be confirmed active when data is successfully collected)
                            for device in devices:
                                if device.status == DeviceStatus.INACTIVE:
                                    # Mark as active when service recovers
                                    device.status = DeviceStatus.ACTIVE
                                    logger.info(
                                        f"Device {device.device_id} marked as ACTIVE "
                                        f"because service {service_id} recovered"
                                    )
                                    # Broadcast device status change via WebSocket
                                    await self._broadcast_device_status_change(device)
                await asyncio.sleep(
                    self.service_registry._service_health_check_interval
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                await asyncio.sleep(
                    self.service_registry._service_health_check_interval
                )

    def register_integration(
        self, device_type: DeviceType, integration: DeviceIntegration
    ):
        """
        Register an integration

        Args:
            device_type: Device type
            integration: Integration instance
        """
        self._integrations[device_type] = integration
        logger.info(f"Registered integration for device type: {device_type.value}")

    def get_integration(self, device_type: DeviceType) -> Optional[DeviceIntegration]:
        """Get integration for device type"""
        return self._integrations.get(device_type)

    def get_all_integrations(self) -> Dict[DeviceType, DeviceIntegration]:
        """Get all registered integrations"""
        return self._integrations.copy()

    def get_device_registry(self) -> DeviceRegistry:
        """Get device registry"""
        return self.device_registry

    def get_discovery_service(self) -> DeviceDiscoveryService:
        """Get device discovery service"""
        return self.discovery_service

    def get_service_registry(self) -> Optional[IntegrationServiceRegistry]:
        """Get integration service registry (if in service mode)"""
        return self.service_registry

    def register_service(
        self,
        service_id: str,
        device_type: DeviceType,
        service_url: str,
        service_name: str,
        version: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[IntegrationServiceClient]:
        """
        Register an integration service (service mode only)

        Args:
            service_id: Unique service identifier
            device_type: Device type
            service_url: Service base URL
            service_name: Integration name
            version: Service version
            metadata: Additional metadata

        Returns:
            IntegrationServiceClient instance or None if not in service mode
        """
        if not self.use_service_mode or not self.service_registry:
            logger.warning(
                "Integration manager is not in service mode. "
                "Cannot register integration service."
            )
            return None

        return self.service_registry.register_service(
            service_id=service_id,
            device_type=device_type,
            service_url=service_url,
            service_name=service_name,
            version=version,
            metadata=metadata,
        )
