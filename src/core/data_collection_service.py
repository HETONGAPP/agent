"""
Data Collection Service
Periodically collects data from integration services and processes through AgentService
Unified data flow: All data goes through AgentService for consistent processing
"""

import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime, UTC

from ..storage.influxdb_client import InfluxDBClient
from .device_registry import DeviceRegistry, DeviceStatus
from .integration_manager import IntegrationManager

if TYPE_CHECKING:
    from ..agent.service import AgentService

logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Service that periodically collects data from integration services
    and writes to InfluxDB
    """

    def __init__(
        self,
        integration_manager: IntegrationManager,
        influx_client: InfluxDBClient,
        agent_service: Optional["AgentService"] = None,
        collection_interval: float = 30.0,
        use_agent_service: bool = True,
        fast_failure_detection: bool = True,
        max_consecutive_failures: int = 3,
        inactive_device_retry_interval: float = 300.0,
    ):
        """
        Initialize data collection service

        Args:
            integration_manager: Integration manager instance
            influx_client: InfluxDB client instance (fallback if agent_service not available)
            agent_service: Optional AgentService instance for unified processing
            collection_interval: Interval for data collection (seconds)
            use_agent_service: If True, route data through AgentService (recommended).
                              If False, write directly to InfluxDB (legacy mode).
            fast_failure_detection: If True, mark device as inactive after consecutive failures
            max_consecutive_failures: Number of consecutive failures before marking device inactive
            inactive_device_retry_interval: Interval for retrying inactive devices (seconds)
        """
        self.integration_manager = integration_manager
        self.influx_client = influx_client
        self.agent_service = agent_service
        self.collection_interval = collection_interval
        self.use_agent_service = use_agent_service
        self.fast_failure_detection = fast_failure_detection
        self.max_consecutive_failures = max_consecutive_failures
        self.inactive_device_retry_interval = inactive_device_retry_interval
        
        # Track consecutive failures for each device
        self._device_failure_count: Dict[str, int] = {}  # device_id -> consecutive failures
        self._device_last_retry: Dict[str, datetime] = {}  # device_id -> last retry time for inactive devices
        
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None
        
        if use_agent_service and not agent_service:
            logger.warning(
                "use_agent_service=True but agent_service not provided. "
                "Falling back to direct InfluxDB writes."
            )

    async def start(self):
        """Start data collection loop"""
        if self._running:
            logger.warning("Data collection service is already running")
            return

        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.debug("Data collection service started")

    async def stop(self):
        """Stop data collection loop"""
        if not self._running:
            return

        self._running = False

        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

        logger.debug("Data collection service stopped")

    async def _collection_loop(self):
        """Main data collection loop"""
        while self._running:
            try:
                await self._collect_all_devices()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}", exc_info=True)
                await asyncio.sleep(self.collection_interval)

    async def _collect_all_devices(self):
        """Collect data from all registered active devices"""
        device_registry = self.integration_manager.get_device_registry()
        service_registry = self.integration_manager.get_service_registry()

        if not service_registry:
            # Not in service mode, skip
            return

        # Get all active devices
        all_devices = device_registry.get_all_devices()
        active_devices = [d for d in all_devices if d.status == DeviceStatus.ACTIVE]

        # Also check inactive devices for retry (if enough time has passed)
        inactive_devices = [d for d in all_devices if d.status == DeviceStatus.INACTIVE]
        devices_to_retry = []
        current_time = datetime.now(UTC)
        
        for device in inactive_devices:
            last_retry = self._device_last_retry.get(device.device_id)
            if not last_retry or (current_time - last_retry).total_seconds() >= self.inactive_device_retry_interval:
                devices_to_retry.append(device)

        if not active_devices and not devices_to_retry:
            logger.debug("No active devices to collect data from")
            return

        logger.debug(
            f"Collecting data from {len(active_devices)} active devices "
            f"and {len(devices_to_retry)} inactive devices (retry)"
        )

        # Collect data from active devices
        for device in active_devices:
            await self._collect_device_data(device, device_registry, service_registry)
        
        # Retry inactive devices
        for device in devices_to_retry:
            await self._collect_device_data(device, device_registry, service_registry, is_retry=True)
            self._device_last_retry[device.device_id] = current_time

    async def _collect_device_data(
        self,
        device,
        device_registry: DeviceRegistry,
        service_registry,
        is_retry: bool = False,
    ):
        """Collect data for a single device"""
        try:
            # Get services for this device type
            services = service_registry.get_services_by_type(device.device_type)

            if not services:
                logger.debug(
                    f"No integration service available for device {device.device_id} "
                    f"(type: {device.device_type.value})"
                )
                return

            # Check service health before attempting collection
            healthy_services = [s for s in services if s.service_info.is_healthy]
            if not healthy_services:
                logger.debug(
                    f"No healthy integration services available for device {device.device_id} "
                    f"(type: {device.device_type.value}). Skipping collection."
                )
                # Immediately mark device as inactive if service is unhealthy
                if device.status == DeviceStatus.ACTIVE:
                    device.mark_inactive()
                    logger.warning(
                        f"Device {device.device_id} marked as INACTIVE "
                        f"because no healthy services available"
                    )
                    # Broadcast device status change via WebSocket
                    await self._broadcast_device_status_change(device)
                # Also handle as failure for fast failure detection tracking
                if self.fast_failure_detection:
                    await self._handle_collection_failure(device.device_id, device_registry)
                return

            # Try to get data from first healthy service
            device_data = None
            collection_success = False
            for service_client in healthy_services:
                try:
                    device_data = await service_client.get_device_data(device.device_id)
                    if device_data:
                        collection_success = True
                        break
                except Exception as e:
                    logger.debug(
                        f"Failed to get data for {device.device_id} from "
                        f"{service_client.service_info.service_id}: {e}"
                    )
                    continue

            # Handle collection result
            if collection_success and device_data:
                # Success: reset failure count and update last_seen
                self._device_failure_count.pop(device.device_id, None)
                device_registry.mark_device_seen(device.device_id)
                
                # If device was inactive and now recovered, mark as active
                if device.status == DeviceStatus.INACTIVE:
                    device.status = DeviceStatus.ACTIVE
                    logger.info(
                        f"Device {device.device_id} recovered and marked as ACTIVE"
                    )
                    self._device_last_retry.pop(device.device_id, None)
                    # Broadcast device status change via WebSocket
                    await self._broadcast_device_status_change(device)
            else:
                # Failure: handle according to fast failure detection
                if self.fast_failure_detection:
                    await self._handle_collection_failure(device.device_id, device_registry)
                else:
                    # Without fast failure detection, just log
                    if not is_retry:
                        logger.debug(
                            f"No data collected for device {device.device_id} "
                            f"(type: {device.device_type.value})"
                        )
                return  # Skip processing if no data

            # Process collected data
            if device_data:
                # Route through AgentService for unified processing (recommended)
                # This ensures all data goes through rule engine and consistent processing
                if self.use_agent_service and self.agent_service:
                    try:
                        # Process through AgentService (includes rule evaluation, storage, etc.)
                        result = await self.agent_service.process_device_data(device_data)
                        logger.debug(
                            f"Collected and processed data for {device.device_id} "
                            f"(type: {device.device_type.value}) via AgentService: "
                            f"status={result.get('status')}, alarms={result.get('alarms_processed', 0)}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to process data for {device.device_id} via AgentService: {e}",
                            exc_info=True,
                        )
                        # Fallback to direct write on error
                        try:
                            self.influx_client.write_device_data(device_data, flush=False)
                            logger.debug(f"Fallback: Direct write to InfluxDB for {device.device_id}")
                        except Exception as write_error:
                            logger.error(
                                f"Failed to write data for {device.device_id} to InfluxDB: {write_error}",
                                exc_info=True,
                            )
                else:
                    # Legacy mode: Direct write to InfluxDB (bypasses rule engine)
                    try:
                        self.influx_client.write_device_data(device_data, flush=False)
                        logger.debug(
                            f"Collected and stored data for {device.device_id} "
                            f"(type: {device.device_type.value}) directly to InfluxDB"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to write data for {device.device_id} to InfluxDB: {e}",
                            exc_info=True,
                        )

        except Exception as e:
            logger.error(
                f"Error collecting data for device {device.device_id}: {e}",
                exc_info=True,
            )
            # Mark as failure if fast failure detection is enabled
            if self.fast_failure_detection:
                await self._handle_collection_failure(device.device_id, device_registry)

    async def _handle_collection_failure(self, device_id: str, device_registry: DeviceRegistry):
        """
        Handle collection failure for a device
        
        Args:
            device_id: Device ID that failed
            device_registry: Device registry instance
        """
        # Increment failure count
        count = self._device_failure_count.get(device_id, 0) + 1
        self._device_failure_count[device_id] = count
        
        device = device_registry.get_device(device_id)
        if not device:
            return
        
        # If max failures reached, mark device as inactive
        if count >= self.max_consecutive_failures:
            if device.status == DeviceStatus.ACTIVE:
                device.mark_inactive()
                logger.warning(
                    f"Device {device_id} marked as INACTIVE after {count} consecutive collection failures. "
                    f"Will retry every {self.inactive_device_retry_interval}s"
                )
                # Reset failure count and record retry time
                self._device_failure_count.pop(device_id, None)
                self._device_last_retry[device_id] = datetime.now(UTC)
                # Broadcast device status change via WebSocket
                await self._broadcast_device_status_change(device)
            elif device.status == DeviceStatus.INACTIVE:
                # Already inactive, just update retry time
                self._device_last_retry[device_id] = datetime.now(UTC)
        else:
            # Not yet at threshold, just log debug
            logger.debug(
                f"Device {device_id} collection failed ({count}/{self.max_consecutive_failures} consecutive failures)"
            )

        # Flush buffer after collecting all devices
        # Note: If using AgentService, it handles flushing internally
        # But we still flush here as a safety measure
        if not self.use_agent_service or not self.agent_service:
            try:
                self.influx_client.flush()
            except Exception as e:
                logger.warning(f"Failed to flush InfluxDB buffer: {e}")

    async def _broadcast_device_status_change(self, device):
        """Broadcast device status change via WebSocket"""
        try:
            from ..agent.dependencies import get_app_state
            from ..agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.DEVICE_STATUS_CHANGED,
                    {
                        "device_id": device.device_id,
                        "status": device.status.value,
                        "device": device.to_dict(),
                    },
                )
        except Exception as e:
            logger.debug(f"Error broadcasting device status change: {e}")
