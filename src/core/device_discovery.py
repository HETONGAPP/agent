"""
Device Discovery Service
Polls for new devices and manages device lifecycle
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from ..models.device_data import DeviceType
from .device_registry import DeviceRegistry, DeviceStatus, RegisteredDevice
from .integration_registry import IntegrationRegistry, get_integration_registry

logger = logging.getLogger(__name__)


class DeviceDiscoveryService:
    """Service for discovering and managing devices"""

    def __init__(
        self,
        device_registry: DeviceRegistry,
        integration_registry: Optional[IntegrationRegistry] = None,
        poll_interval: float = 5.0,
        inactive_timeout: int = 300,
    ):
        """
        Initialize device discovery service

        Args:
            device_registry: Device registry instance
            integration_registry: Integration registry instance
            poll_interval: Polling interval in seconds
            inactive_timeout: Seconds before marking device as inactive
        """
        self.device_registry = device_registry
        self.integration_registry = integration_registry or get_integration_registry()
        self.poll_interval = poll_interval
        self.inactive_timeout = inactive_timeout

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_poll_time = datetime.utcnow()
        self._on_device_discovered: List[Callable[[RegisteredDevice], None]] = []
        self._on_device_removed: List[Callable[[RegisteredDevice], None]] = []

    def on_device_discovered(self, callback: Callable[[RegisteredDevice], None]):
        """
        Register callback for when a new device is discovered

        Args:
            callback: Callback function that receives RegisteredDevice
        """
        self._on_device_discovered.append(callback)

    def on_device_removed(self, callback: Callable[[RegisteredDevice], None]):
        """
        Register callback for when a device is removed

        Args:
            callback: Callback function that receives RegisteredDevice
        """
        self._on_device_removed.append(callback)

    async def start(self):
        """Start the discovery service"""
        if self._running:
            logger.warning("Discovery service is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.debug(
            f"Device discovery service started (poll_interval={self.poll_interval}s)"
        )

    async def stop(self):
        """Stop the discovery service"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.debug("Device discovery service stopped")

    async def _poll_loop(self):
        """Main polling loop"""
        while self._running:
            try:
                await self._poll()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery poll loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def _poll(self):
        """Perform one polling cycle"""
        # Check for new devices
        new_devices = self.device_registry.get_new_devices(self._last_poll_time)

        for device in new_devices:
            logger.info(
                f"Discovered new device: {device.device_id} (type={device.device_type.value}, integration={device.integration_name})"
            )
            # Notify callbacks
            for callback in self._on_device_discovered:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(device)
                    else:
                        callback(device)
                except Exception as e:
                    logger.error(
                        f"Error in device discovered callback: {e}", exc_info=True
                    )

        # Check for inactive devices
        inactive_devices = self.device_registry.get_inactive_devices(
            self.inactive_timeout
        )
        for device in inactive_devices:
            # Only mark as inactive if device is still registered
            # Skip if device was already unregistered (removed by user)
            if device.status != DeviceStatus.INACTIVE:
                # Check if device is still in registry (not unregistered)
                if self.device_registry.get_device(device.device_id) is not None:
                    logger.debug(
                        f"Device {device.device_id} marked as inactive (last_seen: {device.last_seen})"
                    )
                    device.mark_inactive()
                # If device is not in registry, it was unregistered, skip silently

        self._last_poll_time = datetime.utcnow()

    def discover_device(
        self,
        device_id: str,
        device_type: DeviceType,
        integration_name: str,
        metadata: Optional[Dict] = None,
    ) -> RegisteredDevice:
        """
        Manually register/discover a device

        Args:
            device_id: Device ID
            device_type: Device type
            integration_name: Integration name
            metadata: Optional metadata

        Returns:
            Registered device object
        """
        device = self.device_registry.register_device(
            device_id=device_id,
            device_type=device_type,
            integration_name=integration_name,
            metadata=metadata,
        )

        # Trigger discovery callback if this is a new device
        if device.status == DeviceStatus.REGISTERED:
            logger.info(f"Device registered: {device_id} (type={device_type.value})")
            for callback in self._on_device_discovered:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(device))
                    else:
                        callback(device)
                except Exception as e:
                    logger.error(
                        f"Error in device discovered callback: {e}", exc_info=True
                    )

        return device

    def remove_device(self, device_id: str) -> bool:
        """
        Remove a device from registry

        Args:
            device_id: Device ID

        Returns:
            True if device was removed
        """
        device = self.device_registry.get_device(device_id)
        if device and self.device_registry.unregister_device(device_id):
            logger.info(f"Device removed: {device_id}")
            # Notify callbacks
            for callback in self._on_device_removed:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(device))
                    else:
                        callback(device)
                except Exception as e:
                    logger.error(
                        f"Error in device removed callback: {e}", exc_info=True
                    )
            return True
        return False

    def get_all_devices(self) -> List[RegisteredDevice]:
        """Get all registered devices"""
        return self.device_registry.get_all_devices()

    def get_devices_by_type(self, device_type: DeviceType) -> List[RegisteredDevice]:
        """Get devices by type"""
        return self.device_registry.get_devices_by_type(device_type)

    def get_devices_by_integration(
        self, integration_name: str
    ) -> List[RegisteredDevice]:
        """Get devices by integration"""
        return self.device_registry.get_devices_by_integration(integration_name)
