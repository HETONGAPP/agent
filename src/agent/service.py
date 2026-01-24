"""
Agent Service - Main processing service
Integrates rule engine, LLM diagnostic, and Grafana annotation
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.data_flow_tracker import DataFlowTracker
from ..core.device_discovery import DeviceDiscoveryService
from ..core.device_registry import DeviceRegistry, DeviceStatus, RegisteredDevice
from ..core.integration import DeviceIntegration
from ..email import EmailService
from ..grafana import AnnotationService, GrafanaClient
from ..llm_diagnostic import LLMDiagnosticService
from ..models.alarm import Alarm, AlarmSeverity
from ..models.device_data import DeviceData, DeviceType
from ..models.diagnostic import DiagnosticReport
from ..rule_engine import RuleEngine
from ..storage.influxdb_client import InfluxDBClient
from ..storage.site_container import SiteContainerManager

logger = logging.getLogger(__name__)


class AgentService:
    """
    Flexible Agent Service
    Main service that orchestrates rule engine, LLM diagnostic, and Grafana integration
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        llm_diagnostic_service: Optional[LLMDiagnosticService] = None,
        grafana_client: Optional[GrafanaClient] = None,
        annotation_service: Optional[AnnotationService] = None,
        influx_client: Optional[InfluxDBClient] = None,
        email_service: Optional[EmailService] = None,
        integrations: Optional[Dict[DeviceType, DeviceIntegration]] = None,
        device_discovery: Optional[DeviceDiscoveryService] = None,
        flow_tracker: Optional[DataFlowTracker] = None,
        check_device_status: bool = True,
        auto_register_devices: bool = True,
        reject_inactive_devices: bool = False,
    ):
        """
        Initialize agent service

        Args:
            rule_engine: Rule engine instance
            llm_diagnostic_service: Optional LLM diagnostic service
            grafana_client: Optional Grafana client
            annotation_service: Optional annotation service
            influx_client: Optional InfluxDB client
            email_service: Optional email service
            integrations: Optional dictionary of device integrations (DeviceType -> DeviceIntegration)
            device_discovery: Optional device discovery service
            flow_tracker: Optional data flow tracker
            check_device_status: If True, check device status before processing data
            auto_register_devices: If True, automatically register unknown devices from MQTT
            reject_inactive_devices: If True, reject data from INACTIVE devices (instead of auto-recovering)
        """
        self.rule_engine = rule_engine
        self.llm_diagnostic_service = llm_diagnostic_service
        self.grafana_client = grafana_client
        self.annotation_service = annotation_service
        self.influx_client = influx_client
        self.email_service = email_service
        self.integrations = integrations or {}
        self.device_discovery = device_discovery
        self.flow_tracker = flow_tracker
        self.check_device_status = check_device_status  # Whether to check device status before processing
        self.auto_register_devices = auto_register_devices  # Auto-register unknown devices (deprecated, always reject unregistered)
        self.reject_inactive_devices = reject_inactive_devices  # Reject INACTIVE devices instead of auto-recovering
        
        # Auto-diagnostic configuration: disabled by default to save tokens
        # Set to True in config to enable automatic LLM diagnosis on alarm creation
        self._auto_diagnostic_enabled = False
        
        # Initialize site container manager if InfluxDB client is available
        # Container mode can be enabled/disabled via config
        self.container_manager = None
        self.use_containers = True  # Default: enabled, can be set via config
        if influx_client:
            try:
                # Check if container mode is enabled (can be set via config in future)
                # For now, always enable if influx_client is available
                self.container_manager = SiteContainerManager(influx_client)
                logger.info("✓ Site container manager initialized (container mode enabled)")
            except Exception as e:
                logger.warning(f"⚠ Failed to initialize site container manager: {e}")
                self.use_containers = False

        # Data deduplication: Track processed data to avoid duplicate processing
        # Key: f"{device_id}:{timestamp_seconds}", Value: processing_time
        self._processed_keys: Dict[str, float] = {}
        self._dedup_window: float = 3.0  # 3 seconds deduplication window (reduced from 5s to allow more rule evaluations)
        self._dedup_cleanup_interval: float = 60.0  # Cleanup old keys every 60 seconds
        self._last_cleanup: float = time.time()
        
        # Active alarms cache: Track active alarms to prevent duplicates
        # Key: f"{rule_id}:{device_id}", Value: (alarm_id, timestamp)
        self._active_alarms: Dict[str, tuple[str, datetime]] = {}
        self._alarm_dedup_window: float = 60.0  # 60 seconds: if same alarm persists within window, skip creating new
        # Note: We also check database for existing alarms to handle service restarts
        
        # Periodic flush task for InfluxDB buffer (prevent data loss)
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_interval: float = 10.0  # Flush every 10 seconds
        self._running: bool = False

        # Set up device discovery callbacks if discovery service is provided
        if self.device_discovery:
            self.device_discovery.on_device_discovered(self._on_device_discovered)
            self.device_discovery.on_device_removed(self._on_device_removed)

    def _on_device_discovered(self, device: RegisteredDevice):
        """Callback when a new device is discovered"""
        logger.info(
            f"New device discovered: {device.device_id} (type={device.device_type.value})"
        )
        # Integration will be created automatically when needed
        # We can trigger data collection or other actions here if needed

    def _on_device_removed(self, device: RegisteredDevice):
        """Callback when a device is removed"""
        logger.info(
            f"Device removed: {device.device_id} (type={device.device_type.value})"
        )
        # Clean up any device-specific resources if needed
        # Clean up deduplication keys for this device
        keys_to_remove = [k for k in self._processed_keys.keys() if k.startswith(f"{device.device_id}:")]
        for key in keys_to_remove:
            self._processed_keys.pop(key, None)
    
    def _check_recent_alarm_in_db(
        self,
        site_id: str,
        rule_id: str,
        device_id: str,
        alarm_type: str,
        within_seconds: float = 60.0
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a recent alarm exists in database for the same rule and device
        
        Args:
            site_id: Site ID
            rule_id: Rule ID
            device_id: Device ID
            alarm_type: Alarm type
            within_seconds: Time window in seconds to check
            
        Returns:
            Recent alarm dict if found, None otherwise
        """
        try:
            # Use container manager if available (preferred)
            if self.use_containers and self.container_manager:
                container = self.container_manager.get_container(site_id, auto_create=False)
                if container:
                    # Query alarms from the last 'within_seconds' seconds
                    from datetime import timedelta
                    start_time = (datetime.now(UTC) - timedelta(seconds=within_seconds)).isoformat()
                    alarms = container.query_alarms(
                        start_time=start_time,
                        device_ids=[device_id],
                        alarm_type=alarm_type,
                        limit=10,
                        deduplicate=False
                    )
                    
                    # Find alarm with matching rule_id
                    for alarm in alarms:
                        alarm_rule_id = alarm.get("metadata", {}).get("rule_id") if isinstance(alarm.get("metadata"), dict) else None
                        if alarm_rule_id == rule_id:
                            return alarm
                    return None
            
            # Fallback to direct influx_client
            if self.influx_client:
                from datetime import timedelta
                start_time = (datetime.now(UTC) - timedelta(seconds=within_seconds)).isoformat()
                alarms = self.influx_client.query_alarms(
                    start_time=start_time,
                    site_id=site_id,
                    device_type=None,  # Don't filter by device_type, use device_id instead
                    alarm_type=alarm_type,
                    limit=10
                )
                
                # Filter by device_id and rule_id
                for alarm in alarms:
                    alarm_device_id = alarm.get("device_id") or alarm.get("metadata", {}).get("device_id") if isinstance(alarm.get("metadata"), dict) else None
                    alarm_rule_id = alarm.get("metadata", {}).get("rule_id") if isinstance(alarm.get("metadata"), dict) else None
                    if alarm_device_id == device_id and alarm_rule_id == rule_id:
                        return alarm
            
            return None
        except Exception as e:
            logger.debug(f"Error checking recent alarm in database: {e}")
            return None

    def _generate_dedup_key(self, device_data: DeviceData) -> str:
        """
        Generate deduplication key for device data
        
        Args:
            device_data: DeviceData to generate key for
            
        Returns:
            Deduplication key string
        """
        # Use device_id and timestamp (rounded to seconds) for deduplication
        timestamp_seconds = int(device_data.timestamp.timestamp())
        return f"{device_data.device_id}:{timestamp_seconds}"

    def _is_duplicate(self, device_data: DeviceData) -> bool:
        """
        Check if device data is a duplicate
        
        Args:
            device_data: DeviceData to check
            
        Returns:
            True if duplicate, False otherwise
        """
        dedup_key = self._generate_dedup_key(device_data)
        current_time = time.time()
        
        # Check if key exists and is within deduplication window
        if dedup_key in self._processed_keys:
            processing_time = self._processed_keys[dedup_key]
            if current_time - processing_time < self._dedup_window:
                return True
        
        # Cleanup old keys periodically
        if current_time - self._last_cleanup > self._dedup_cleanup_interval:
            self._cleanup_old_keys(current_time)
            self._last_cleanup = current_time
        
        # Mark as processed
        self._processed_keys[dedup_key] = current_time
        return False

    def _cleanup_old_keys(self, current_time: float):
        """Clean up old deduplication keys outside the window"""
        keys_to_remove = [
            key for key, processing_time in self._processed_keys.items()
            if current_time - processing_time > self._dedup_window
        ]
        for key in keys_to_remove:
            self._processed_keys.pop(key, None)
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old deduplication keys")

    async def start(self):
        """Start periodic flush task for InfluxDB buffer"""
        if self._running:
            return
        self._running = True
        if self.influx_client:
            self._flush_task = asyncio.create_task(self._periodic_flush())
            logger.debug("Started periodic InfluxDB buffer flush task")

    async def stop(self):
        """Stop periodic flush task and perform final flush"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush on shutdown
        if self.influx_client:
            try:
                self.influx_client.flush()
                logger.debug("Final InfluxDB buffer flush completed")
            except Exception as e:
                logger.warning(f"Failed to perform final flush: {e}")

    async def _periodic_flush(self):
        """Periodically flush InfluxDB buffer to prevent data loss"""
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                if self.influx_client and self._running:
                    try:
                        self.influx_client.flush()
                        logger.debug("Periodic InfluxDB buffer flush completed")
                    except Exception as e:
                        logger.error(f"Periodic flush failed: {e}", exc_info=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush task: {e}", exc_info=True)
                await asyncio.sleep(self._flush_interval)

    async def process_webhook_alarm(
        self,
        webhook_data: Dict[str, Any],
        device_data: Optional[DeviceData] = None,
    ) -> Dict[str, Any]:
        """
        Process alarm from Grafana webhook

        Args:
            webhook_data: Parsed webhook data
            device_data: Optional device data

        Returns:
            Processing result with alarms and diagnostics
        """
        try:
            # Create Alarm object from webhook data
            alarm = self._create_alarm_from_webhook(webhook_data)

            # Create DeviceData if not provided
            if device_data is None:
                device_data = self._create_device_data_from_webhook(webhook_data)

            # Check device status before processing (same as process_device_data)
            if self.check_device_status:
                from ..agent.dependencies import get_device_registry
                device_registry = get_device_registry()
                registered_device = device_registry.get_device(device_data.device_id)
                
                if not registered_device:
                    # Device not registered - reject
                    logger.warning(
                        f"✗ Rejecting webhook data from unregistered device {device_data.device_id}. "
                        f"Device must be registered before data can be processed."
                    )
                    return {
                        "status": "rejected",
                        "message": f"Device {device_data.device_id} is not registered. Webhook data rejected.",
                        "device_id": device_data.device_id,
                        "device_status": "unregistered",
                        "alarms_processed": 0,
                    }
                elif registered_device.status == DeviceStatus.INACTIVE:
                    if self.reject_inactive_devices:
                        # Reject data from INACTIVE devices
                        logger.warning(
                            f"✗ Rejecting webhook data from INACTIVE device {device_data.device_id}. "
                            f"Device must be ACTIVE to process data."
                        )
                        return {
                            "status": "rejected",
                            "message": f"Device {device_data.device_id} is INACTIVE. Webhook data rejected.",
                            "device_id": device_data.device_id,
                            "device_status": "INACTIVE",
                            "alarms_processed": 0,
                        }
                    else:
                        # Auto-recover INACTIVE device
                        registered_device.status = DeviceStatus.ACTIVE
                        device_registry.mark_device_seen(device_data.device_id)
                        logger.info(
                            f"✓ Device {device_data.device_id} recovered (received webhook data while INACTIVE). "
                            f"Status updated to ACTIVE."
                        )
                elif registered_device.status == DeviceStatus.ACTIVE:
                    # Active device, update last_seen
                    device_registry.mark_device_seen(device_data.device_id)

            # Evaluate rules
            alarms = self.rule_engine.evaluate(device_data)

            # If no rules matched, use the webhook alarm
            if not alarms:
                alarms = [alarm]

            # Process each alarm
            results = []
            for alarm in alarms:
                result = await self._process_alarm(alarm, device_data, webhook_data)
                results.append(result)

            # Flush InfluxDB buffer if using async writes
            if self.influx_client:
                try:
                    self.influx_client.flush()
                except Exception as e:
                    logger.warning(f"Failed to flush InfluxDB buffer: {e}")

            return {
                "status": "success",
                "alarms_processed": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Failed to process webhook alarm: {e}", exc_info=True)
            # Ensure InfluxDB buffer is flushed even on error
            if self.influx_client:
                try:
                    self.influx_client.flush()
                except Exception as flush_error:
                    logger.warning(f"Failed to flush InfluxDB buffer on error: {flush_error}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def get_device_data_from_service(
        self, device_id: str, device_type: DeviceType
    ) -> Optional[DeviceData]:
        """
        Get device data from integration service (service mode)

        Args:
            device_id: Device ID
            device_type: Device type

        Returns:
            DeviceData or None if error
        """
        # Data collection is now manual via API endpoints
        # This method is deprecated - use the generic API endpoint instead
        return None

    async def process_device_data(
        self,
        device_data: Optional[DeviceData] = None,
        device_id: Optional[str] = None,
        device_type: Optional[DeviceType] = None,
        history: Optional[List[DeviceData]] = None,
    ) -> Dict[str, Any]:
        """
        Process device data with deduplication
        
        Checks for duplicate data within the deduplication window before processing.
        This prevents duplicate processing when the same data arrives from multiple sources
        (e.g., MQTT and integration service collection).
        """
        """
        Process device data (evaluate rules and generate diagnostics)

        Args:
            device_data: Device data to process (if provided)
            device_id: Device ID (if device_data not provided, fetch from service)
            device_type: Device type (required if device_id provided)
            history: Optional historical data

        Returns:
            Processing result
        """
        try:
            # If device_data not provided, try to get from integration service
            if device_data is None:
                if device_id and device_type:
                    device_data = await self.get_device_data_from_service(
                        device_id, device_type
                    )
                    if not device_data:
                        return {
                            "status": "error",
                            "error": f"Failed to get device data for {device_id} from integration service",
                        }
                else:
                    return {
                        "status": "error",
                        "error": "device_data or (device_id + device_type) required",
                    }
            
            # Track data flow: input stage
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="input",
                    data_id=device_data.device_id,
                    metadata={
                        "device_type": device_data.device_type.value,
                        "source": device_data.source,
                        "site_id": device_data.site_id,
                    },
                )

            # Check for duplicate data (deduplication)
            if self._is_duplicate(device_data):
                logger.debug(
                    f"⏭ [AgentService] Skipping duplicate data: "
                    f"device_id={device_data.device_id}, "
                    f"timestamp={device_data.timestamp}, "
                    f"source={device_data.source}"
                )
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="deduplication",
                        data_id=device_data.device_id,
                        status="duplicate",
                    )
                return {
                    "status": "duplicate",
                    "message": "Data already processed within deduplication window",
                    "device_id": device_data.device_id,
                    "timestamp": device_data.timestamp.isoformat(),
                    "alarms_processed": 0,
                    "data_stored": False,
                }
            
            # Check device status: Only process data from ACTIVE devices
            # If device is INACTIVE but we receive data, it means device recovered
            if self.check_device_status:
                from ..agent.dependencies import get_device_registry
                device_registry = get_device_registry()
                registered_device = device_registry.get_device(device_data.device_id)
                
                if registered_device:
                    if registered_device.status == DeviceStatus.INACTIVE:
                        if self.reject_inactive_devices:
                            # Reject data from INACTIVE devices
                            logger.warning(
                                f"✗ Rejecting data from INACTIVE device {device_data.device_id}. "
                                f"Device must be ACTIVE to process data."
                            )
                            if self.flow_tracker:
                                self.flow_tracker.track(
                                    stage="device_status_check",
                                    data_id=device_data.device_id,
                                    metadata={"status": "INACTIVE", "action": "rejected"},
                                    status="rejected",
                                )
                            return {
                                "status": "rejected",
                                "message": f"Device {device_data.device_id} is INACTIVE. Data rejected.",
                                "device_id": device_data.device_id,
                                "device_status": "INACTIVE",
                                "alarms_processed": 0,
                                "data_stored": False,
                            }
                        else:
                            # Device was inactive but we received data - device recovered!
                            previous_status = registered_device.status
                            registered_device.status = DeviceStatus.ACTIVE
                            device_registry.mark_device_seen(device_data.device_id)
                            logger.info(
                                f"✓ Device {device_data.device_id} recovered (received data while INACTIVE). "
                                f"Status updated to ACTIVE."
                            )
                            # Broadcast status change
                            await self._broadcast_device_status_changed(
                                device_data.device_id, 
                                previous_status, 
                                DeviceStatus.ACTIVE,
                                registered_device
                            )
                            if self.flow_tracker:
                                self.flow_tracker.track(
                                    stage="device_recovery",
                                    data_id=device_data.device_id,
                                    metadata={"previous_status": "INACTIVE"},
                                    status="recovered",
                                )
                    elif registered_device.status == DeviceStatus.ACTIVE:
                        # Active device, update last_seen
                        device_registry.mark_device_seen(device_data.device_id)
                    elif registered_device.status == DeviceStatus.REGISTERED:
                        # Newly registered device, update to ACTIVE on first data
                        previous_status = registered_device.status
                        device_registry.mark_device_seen(device_data.device_id)
                        logger.debug(
                            f"Device {device_data.device_id} activated (first data received)"
                        )
                        # Broadcast status change from REGISTERED to ACTIVE
                        updated_device = device_registry.get_device(device_data.device_id)
                        if updated_device and updated_device.status == DeviceStatus.ACTIVE:
                            await self._broadcast_device_status_changed(
                                device_data.device_id,
                                previous_status,
                                DeviceStatus.ACTIVE,
                                updated_device
                            )
                else:
                    # Device not registered - auto-register it
                    logger.info(
                        f"🔄 Auto-registering device {device_data.device_id} from MQTT data "
                        f"(type={device_data.device_type.value}, site_id={device_data.site_id})"
                    )
                    
                    # Prepare metadata for auto-registration
                    metadata = {
                        "site_id": device_data.site_id,
                        "source": device_data.source or "mqtt",
                        "registered_via": "auto_mqtt",
                        "registered_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if device_data.site_name:
                        metadata["site_name"] = device_data.site_name
                    
                    # Auto-register the device
                    try:
                        registered_device = device_registry.register_device(
                            device_id=device_data.device_id,
                            device_type=device_data.device_type,
                            integration_name="mqtt",  # Use "mqtt" as integration name for auto-registered devices
                            metadata=metadata,
                        )
                        
                        if registered_device.status == DeviceStatus.UNREGISTERED:
                            # Registration was rejected (e.g., device was deleted)
                            logger.warning(
                                f"✗ Auto-registration rejected for device {device_data.device_id}. "
                                f"Device may have been deleted. Data rejected."
                            )
                            if self.flow_tracker:
                                self.flow_tracker.track(
                                    stage="device_status_check",
                                    data_id=device_data.device_id,
                                    metadata={
                                        "status": "unregistered",
                                        "action": "rejected",
                                        "device_type": device_data.device_type.value,
                                        "source": device_data.source,
                                    },
                                    status="rejected",
                                )
                            return {
                                "status": "rejected",
                                "message": f"Device {device_data.device_id} auto-registration rejected. Device may have been deleted.",
                                "device_id": device_data.device_id,
                                "device_status": "unregistered",
                                "alarms_processed": 0,
                                "data_stored": False,
                            }
                        
                        # Mark device as seen (will activate it)
                        device_registry.mark_device_seen(device_data.device_id)
                        
                        logger.info(
                            f"✓ Device {device_data.device_id} auto-registered successfully "
                            f"(status={registered_device.status.value})"
                        )
                        
                        # Broadcast device added event
                        from ..agent.dependencies import get_app_state
                        from ..agent.websocket_manager import EventType
                        app_state = get_app_state()
                        websocket_manager = app_state.get("websocket_manager")
                        if websocket_manager:
                            await websocket_manager.broadcast(
                                EventType.DEVICE_ADDED, {"data": registered_device.to_dict()}
                            )
                        
                        if self.flow_tracker:
                            self.flow_tracker.track(
                                stage="device_auto_registration",
                                data_id=device_data.device_id,
                                metadata={
                                    "device_type": device_data.device_type.value,
                                    "source": device_data.source,
                                    "site_id": device_data.site_id,
                                },
                                status="registered",
                            )
                        
                        # Auto-create rules for this device if site_id is provided
                        if device_data.site_id:
                            try:
                                from ..agent.dependencies import get_site_manager
                                site_manager = get_site_manager()
                                if site_manager:
                                    rules_created = site_manager.create_device_rules(
                                        device_id=device_data.device_id,
                                        device_type=device_data.device_type.value,
                                        site_id=device_data.site_id
                                    )
                                    logger.info(f"Auto-created {rules_created} rules for auto-registered device {device_data.device_id} in site {device_data.site_id}")
                            except Exception as e:
                                logger.warning(f"Failed to auto-create rules for device {device_data.device_id}: {e}")
                        
                    except Exception as e:
                        logger.error(
                            f"✗ Failed to auto-register device {device_data.device_id}: {e}",
                            exc_info=True
                        )
                        if self.flow_tracker:
                            self.flow_tracker.track(
                                stage="device_auto_registration",
                                data_id=device_data.device_id,
                                metadata={
                                    "error": str(e),
                                    "device_type": device_data.device_type.value,
                                    "source": device_data.source,
                                },
                                status="failed",
                            )
                        return {
                            "status": "error",
                            "message": f"Failed to auto-register device {device_data.device_id}: {str(e)}",
                            "device_id": device_data.device_id,
                            "device_status": "unregistered",
                            "alarms_processed": 0,
                            "data_stored": False,
                        }
            
            # Store device data to InfluxDB first (regardless of alarms)
            # Use site container if available and enabled, otherwise fallback to direct influx_client
            if self.use_containers and self.container_manager and device_data.site_id:
                try:
                    # Get site container and write to it
                    container = self.container_manager.get_container(device_data.site_id, auto_create=True)
                    container.write_device_data(device_data, flush=False)
                    logger.debug(
                        f"✓ [AgentService] Stored {device_data.device_type.value} data to site container: "
                        f"site_id={device_data.site_id}, device_id={device_data.device_id}, "
                        f"fields={list(device_data.data.keys())}"
                    )
                except Exception as e:
                    logger.error(
                        f"✗ [AgentService] Failed to store device data to site container: {e}",
                        exc_info=True,
                    )
            elif self.influx_client:
                try:
                    logger.debug(
                        f"  [AgentService] Writing to InfluxDB (legacy mode) - device_id: {device_data.device_id}, "
                        f"device_type: {device_data.device_type.value}, "
                        f"fields: {list(device_data.data.keys())}"
                    )
                    # Fallback to direct influx_client (legacy mode)
                    self.influx_client.write_device_data(device_data, flush=False)
                    logger.debug(
                        f"✓ [AgentService] Stored {device_data.device_type.value} data to InfluxDB: "
                        f"device_id={device_data.device_id}, "
                        f"fields={list(device_data.data.keys())}, "
                        f"timestamp={device_data.timestamp}"
                    )
                except Exception as e:
                    logger.error(
                        f"✗ [AgentService] Failed to store device data to InfluxDB: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "⚠ [AgentService] InfluxDB client not available, cannot store data"
                )

            # Track data flow: rule evaluation stage
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="rule_evaluation",
                    data_id=device_data.device_id,
                )

            # Evaluate rules
            alarms = self.rule_engine.evaluate(device_data, history)
            logger.info(
                f"[AgentService] Rule evaluation for {device_data.device_id} (site: {device_data.site_id}): "
                f"Generated {len(alarms)} alarms before deduplication"
            )
            
            # Deduplicate alarms: Check if same alarm already exists
            # Strategy:
            # 1. Check memory cache first (fast)
            # 2. If not in cache, check database for recent alarms (handles service restarts)
            # 3. If alarm exists within dedup window, skip creating new alarm
            deduplicated_alarms = []
            current_time = datetime.now(UTC)
            
            for alarm in alarms:
                # Generate deduplication key: rule_id + device_id
                rule_id = alarm.metadata.get("rule_id", "UNKNOWN")
                device_id = alarm.metadata.get("device_id", device_data.device_id)
                alarm_type = alarm.alarm_type
                dedup_key = f"{rule_id}:{device_id}"
                
                # Step 1: Check memory cache first
                should_skip = False
                if dedup_key in self._active_alarms:
                    existing_alarm_id, existing_timestamp = self._active_alarms[dedup_key]
                    time_since_existing = (current_time - existing_timestamp).total_seconds()
                    
                    if time_since_existing < self._alarm_dedup_window:
                        logger.debug(
                            f"[AgentService] Skipping duplicate alarm (cache): {alarm_type} for device {device_id} "
                            f"(rule_id: {rule_id}, existing alarm {existing_alarm_id} from {time_since_existing:.1f}s ago)"
                        )
                        should_skip = True
                    else:
                        # Alarm exists but is old, remove from cache
                        logger.debug(f"Removing old alarm from cache: {dedup_key} (age: {time_since_existing:.1f}s)")
                        self._active_alarms.pop(dedup_key, None)
                
                # Step 2: If not in cache, check database for recent alarms (within dedup window)
                if not should_skip and device_data.site_id:
                    try:
                        # Query database for recent alarms with same rule_id and device_id
                        recent_alarm = self._check_recent_alarm_in_db(
                            site_id=device_data.site_id,
                            rule_id=rule_id,
                            device_id=device_id,
                            alarm_type=alarm_type,
                            within_seconds=self._alarm_dedup_window
                        )
                        
                        if recent_alarm:
                            logger.debug(
                                f"[AgentService] Skipping duplicate alarm (database): {alarm_type} for device {device_id} "
                                f"(rule_id: {rule_id}, found recent alarm {recent_alarm.get('alarm_id')} in database)"
                            )
                            # Update cache with database alarm info
                            self._active_alarms[dedup_key] = (
                                recent_alarm.get('alarm_id', alarm.alarm_id),
                                current_time
                            )
                            should_skip = True
                    except Exception as e:
                        logger.warning(f"Failed to check database for duplicate alarm: {e}")
                        # Continue processing if database check fails
                
                if should_skip:
                    continue
                
                # Add to active alarms cache and process
                self._active_alarms[dedup_key] = (alarm.alarm_id, current_time)
                logger.info(
                    f"[AgentService] Processing new alarm: {alarm.alarm_id} "
                    f"(rule_id: {rule_id}, alarm_type: {alarm_type}, device_id: {device_id})"
                )
                deduplicated_alarms.append(alarm)
            
            # Clean up old active alarms from cache (older than dedup window)
            keys_to_remove = []
            for key, (_, timestamp) in self._active_alarms.items():
                age = (current_time - timestamp).total_seconds()
                if age > self._alarm_dedup_window:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                self._active_alarms.pop(key, None)
            
            alarms = deduplicated_alarms
            
            # Track rule evaluation result
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="rule_evaluation_complete",
                    data_id=device_data.device_id,
                    metadata={"alarms_count": len(alarms), "deduplicated": True},
                    status="success" if alarms else "no_alarms",
                )

            # Broadcast stats update after processing device data (to update last_seen and device status)
            try:
                from ..agent.dependencies import get_app_state
                from ..agent.websocket_manager import EventType
                
                app_state = get_app_state()
                websocket_manager = app_state.get("websocket_manager")
                if websocket_manager:
                    # Get quick stats to include in broadcast
                    stats = await self._get_quick_stats(site_id=device_data.site_id)
                    
                    await websocket_manager.broadcast(
                        EventType.STATS_UPDATED,
                        {
                            "device_id": device_data.device_id,
                            "site_id": device_data.site_id,
                            "device_type": device_data.device_type.value,
                            "stats": stats,  # Include stats to avoid frontend HTTP request
                        },
                    )
            except Exception as e:
                logger.debug(f"Error broadcasting stats update: {e}")

            if not alarms:
                # Flush InfluxDB buffer even if no alarms
                if self.influx_client:
                    try:
                        logger.debug(
                            "  [AgentService] Flushing InfluxDB buffer (no alarms)"
                        )
                        self.influx_client.flush()
                        logger.debug("  ✓ [AgentService] InfluxDB buffer flushed")
                    except Exception as e:
                        logger.error(
                            f"  ✗ [AgentService] Failed to flush InfluxDB buffer: {e}",
                            exc_info=True,
                        )

                return {
                    "status": "success",
                    "alarms_processed": 0,
                    "message": "No alarms generated",
                    "data_stored": True,
                }

            # Process alarms in parallel for better performance
            async def process_single_alarm(alarm: Alarm) -> Dict[str, Any]:
                """Process a single alarm with tracking"""
                # Track alarm processing
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="alarm_processing",
                        data_id=device_data.device_id,
                        metadata={"alarm_type": alarm.alarm_type, "severity": alarm.severity.value},
                    )
                
                # Find matching rule
                rule = self.rule_engine.get_rule(alarm.metadata.get("rule_id", ""))
                result = await self._process_alarm(alarm, device_data, rule=rule)
                
                # Track alarm processing complete
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="alarm_processing_complete",
                        data_id=device_data.device_id,
                        metadata={"alarm_type": alarm.alarm_type},
                        status=result.get("status", "success"),
                    )
                
                return result

            # Process all alarms in parallel
            if len(alarms) > 1:
                logger.debug(f"Processing {len(alarms)} alarms in parallel")
                tasks = [process_single_alarm(alarm) for alarm in alarms]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Handle exceptions in results
                processed_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Error processing alarm {i}: {result}",
                            exc_info=True,
                        )
                        processed_results.append({
                            "status": "error",
                            "error": str(result),
                            "alarm": alarms[i].to_dict() if i < len(alarms) else None,
                        })
                    else:
                        processed_results.append(result)
                results = processed_results
            else:
                # Single alarm, no need for parallel processing
                results = [await process_single_alarm(alarms[0])]

            # Flush InfluxDB buffer if using async writes
            if self.influx_client:
                try:
                    logger.debug(
                        f"  [AgentService] Flushing InfluxDB buffer ({len(alarms)} alarms processed)"
                    )
                    self.influx_client.flush()
                    logger.debug("  ✓ [AgentService] InfluxDB buffer flushed")
                except Exception as e:
                    logger.error(
                        f"  ✗ [AgentService] Failed to flush InfluxDB buffer: {e}",
                        exc_info=True,
                    )

            return {
                "status": "success",
                "alarms_processed": len(results),
                "results": results,
                "data_stored": True,
            }

        except Exception as e:
            logger.error(f"Failed to process device data: {e}", exc_info=True)
            # Ensure InfluxDB buffer is flushed even on error
            if self.influx_client:
                try:
                    self.influx_client.flush()
                except Exception as flush_error:
                    logger.warning(f"Failed to flush InfluxDB buffer on error: {flush_error}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def _process_alarm(
        self,
        alarm: Alarm,
        device_data: DeviceData,
        webhook_data: Optional[Dict[str, Any]] = None,
        rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a single alarm"""
        result = {
            "alarm": alarm.to_dict(),
            "diagnostic": None,
            "annotation": None,
            "stored": False,
        }

        # Generate LLM diagnostic if service available and auto_diagnostic is enabled
        # NOTE: Auto-diagnostic is disabled by default to save tokens.
        # Use manual trigger API endpoints instead:
        # - POST /api/v1/sites/{site_id}/diagnostics/generate
        # - POST /api/v1/alarms/{alarm_id}/diagnostic
        auto_diagnostic_enabled = getattr(self, '_auto_diagnostic_enabled', False)
        if self.llm_diagnostic_service and auto_diagnostic_enabled:
            # Track LLM diagnostic start
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="llm_diagnostic",
                    data_id=device_data.device_id,
                    metadata={"alarm_type": alarm.alarm_type},
                )
            
            try:
                diagnostic_report = (
                    await self.llm_diagnostic_service.generate_diagnostic(
                        alarm=alarm,
                        device_data=device_data,
                        rule=rule,
                    )
                )
                result["diagnostic"] = diagnostic_report.to_dict()
                
                # Track LLM diagnostic complete
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="llm_diagnostic_complete",
                        data_id=device_data.device_id,
                        metadata={
                            "alarm_type": alarm.alarm_type,
                            "risk_level": diagnostic_report.risk_level,
                        },
                    )

                # Create Grafana annotation if service available
                if self.annotation_service:
                    try:
                        annotation = await self.annotation_service.create_diagnostic_annotation_async(
                            alarm=alarm,
                            diagnostic_report=diagnostic_report,
                            dashboard_id=webhook_data.get("dashboard_id")
                            if webhook_data
                            else None,
                            panel_id=webhook_data.get("panel_id")
                            if webhook_data
                            else None,
                        )
                        result["annotation"] = annotation
                    except Exception as e:
                        logger.warning(f"Failed to create annotation: {e}", exc_info=True)
                        result["annotation_error"] = str(e)

            except Exception as e:
                logger.error(f"Failed to generate diagnostic: {e}", exc_info=True)
                result["diagnostic_error"] = str(e)
        else:
            # Auto-diagnostic disabled - diagnostic will be generated manually via API
            logger.debug(f"Auto-diagnostic disabled for alarm {alarm.alarm_id}. Use manual trigger API to generate diagnostic.")

        # Store alarm and diagnostic to InfluxDB if available
        if self.influx_client:
            try:
                # Use batch write (flush=False) for better performance
                # Get site_id: prefer from device registration metadata, fallback to device_data
                site_id = None
                if device_data:
                    # First, try to get site_id from device registration metadata
                    from ..agent.dependencies import get_device_registry
                    device_registry = get_device_registry()
                    registered_device = device_registry.get_device(device_data.device_id)
                    if registered_device and registered_device.metadata:
                        site_id = registered_device.metadata.get("site_id")
                    
                    # Fallback to device_data.site_id if not found in registration
                    if not site_id:
                        site_id = device_data.site_id
                
                # Use site container if available and enabled, otherwise fallback to direct influx_client
                if self.use_containers and self.container_manager and site_id:
                    try:
                        container = self.container_manager.get_container(site_id, auto_create=True)
                        container.write_alarm(alarm, flush=False)
                        if result["diagnostic"]:
                            # Store diagnostic metadata
                            diagnostic_dict = result["diagnostic"].copy()
                            if "metadata" not in diagnostic_dict:
                                diagnostic_dict["metadata"] = {}
                            # Copy device_id, device_type, and alarm_type from alarm metadata to diagnostic metadata
                            if alarm.metadata.get("device_id"):
                                diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                            if alarm.metadata.get("device_type"):
                                diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                            diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                            container.write_diagnostic(alarm.alarm_id, diagnostic_dict)
                        result["stored"] = True
                        logger.debug(f"✓ Stored alarm to site container: site_id={site_id}, alarm_id={alarm.alarm_id}")
                    except Exception as e:
                        logger.warning(f"Failed to store to site container (first attempt): {e}")
                        result["storage_error"] = str(e)
                        result["stored"] = False
                        
                        # Retry storage with exponential backoff
                        max_retries = 2
                        retry_delay = 0.5
                        for retry in range(max_retries):
                            try:
                                await asyncio.sleep(retry_delay)
                                logger.info(f"Retrying alarm storage to container (attempt {retry + 2}/{max_retries + 1})")
                                container = self.container_manager.get_container(site_id, auto_create=True)
                                container.write_alarm(alarm, flush=False)
                                if result["diagnostic"]:
                                    diagnostic_dict = result["diagnostic"].copy()
                                    if "metadata" not in diagnostic_dict:
                                        diagnostic_dict["metadata"] = {}
                                    if alarm.metadata.get("device_id"):
                                        diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                                    if alarm.metadata.get("device_type"):
                                        diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                                    diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                                    container.write_diagnostic(alarm.alarm_id, diagnostic_dict)
                                result["stored"] = True
                                result["storage_error"] = None
                                logger.info(f"✓ Alarm storage to container succeeded on retry {retry + 2}")
                                break
                            except Exception as retry_error:
                                logger.warning(f"Alarm storage retry {retry + 2} failed: {retry_error}")
                                retry_delay *= 2
                                if retry == max_retries - 1:
                                    logger.error(f"✗ Alarm storage failed after {max_retries + 1} attempts: {retry_error}")
                                    result["storage_error"] = f"Failed after {max_retries + 1} attempts: {str(retry_error)}"
                elif self.influx_client:
                    # Fallback to direct influx_client (legacy mode)
                    self.influx_client.write_alarm(alarm, flush=False, site_id=site_id)
                    if result["diagnostic"]:
                        # Store diagnostic metadata
                        diagnostic_dict = result["diagnostic"].copy()
                        if "metadata" not in diagnostic_dict:
                            diagnostic_dict["metadata"] = {}
                        # Copy device_id, device_type, and alarm_type from alarm metadata to diagnostic metadata
                        if alarm.metadata.get("device_id"):
                            diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                        if alarm.metadata.get("device_type"):
                            diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                        diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                        self.influx_client.write_diagnostic(
                            alarm.alarm_id, diagnostic_dict, site_id=site_id
                        )
                    result["stored"] = True
                else:
                    result["stored"] = False
                    result["storage_error"] = "No InfluxDB client or container manager available"
            except Exception as e:
                logger.warning(f"Failed to store alarm to InfluxDB (first attempt): {e}")
                # Retry storage with exponential backoff
                result["stored"] = False
                result["storage_error"] = str(e)
                
                # Retry up to 2 more times with exponential backoff
                max_retries = 2
                retry_delay = 0.5  # Start with 0.5 seconds
                for retry in range(max_retries):
                    try:
                        await asyncio.sleep(retry_delay)
                        logger.info(f"Retrying alarm storage (attempt {retry + 2}/{max_retries + 1})")
                        
                        if self.use_containers and self.container_manager and site_id:
                            container = self.container_manager.get_container(site_id, auto_create=True)
                            if container:
                                container.write_alarm(alarm, flush=False)
                                if result["diagnostic"]:
                                    container.write_diagnostic(alarm.alarm_id, result["diagnostic"])
                                result["stored"] = True
                                result["storage_error"] = None
                                logger.info(f"✓ Alarm storage succeeded on retry {retry + 2}")
                                break
                        elif self.influx_client:
                            self.influx_client.write_alarm(alarm, flush=False, site_id=site_id)
                            if result["diagnostic"]:
                                diagnostic_dict = result["diagnostic"].copy()
                                if "metadata" not in diagnostic_dict:
                                    diagnostic_dict["metadata"] = {}
                                if alarm.metadata.get("device_id"):
                                    diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                                if alarm.metadata.get("device_type"):
                                    diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                                diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                                self.influx_client.write_diagnostic(alarm.alarm_id, diagnostic_dict, site_id=site_id)
                            result["stored"] = True
                            result["storage_error"] = None
                            logger.info(f"✓ Alarm storage succeeded on retry {retry + 2}")
                            break
                    except Exception as retry_error:
                        logger.warning(f"Alarm storage retry {retry + 2} failed: {retry_error}")
                        retry_delay *= 2  # Exponential backoff
                        if retry == max_retries - 1:
                            # Final retry failed
                            logger.error(f"✗ Alarm storage failed after {max_retries + 1} attempts: {retry_error}")
                            result["storage_error"] = f"Failed after {max_retries + 1} attempts: {str(retry_error)}"

        # Broadcast alarm creation via WebSocket
        await self._broadcast_alarm_created(alarm, result)
        
        # Publish event via event bus
        try:
            from ..agent.dependencies import get_app_state
            from ..core.event_bus import get_event_bus, EventType as EventBusType
            app_state = get_app_state()
            event_bus = app_state.get("event_bus")
            if event_bus:
                await event_bus.publish(
                    EventBusType.ALARM_CREATED,
                    {
                        "alarm": alarm.to_dict(),
                        "result": result,
                    }
                )
        except Exception as e:
            logger.debug(f"Error publishing alarm event: {e}")
        
        # Invalidate query cache for alarms
        try:
            from ..agent.dependencies import get_app_state
            app_state = get_app_state()
            query_cache = app_state.get("query_cache")
            if query_cache:
                # Invalidate alarms and stats cache
                query_cache.invalidate("alarms")
                query_cache.invalidate("alarm_stats")
                logger.debug("Invalidated alarm query cache after new alarm creation")
        except Exception as e:
            logger.debug(f"Error invalidating cache: {e}")
        
        # Send email if service available
        if self.email_service and result["diagnostic"]:
            try:
                diagnostic_report_obj = DiagnosticReport.from_dict(result["diagnostic"])
                email_sent = await self.email_service.send_alarm_email(
                    alarm=alarm,
                    diagnostic_report=diagnostic_report_obj,
                    device_data=device_data.to_dict() if device_data else None,
                )
                result["email_sent"] = email_sent
            except Exception as e:
                logger.warning(f"Failed to send email: {e}", exc_info=True)
                result["email_sent"] = False
                result["email_error"] = str(e)

        # Broadcast alarm creation via WebSocket
        await self._broadcast_alarm_created(alarm, result)

        return result

    async def _get_quick_stats(self, site_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get quick statistics for WebSocket broadcast
        Optimized to return only essential stats without heavy queries
        
        Args:
            site_id: Optional site ID to filter stats
            
        Returns:
            Dictionary with alarm, device, and diagnostic stats
        """
        stats = {
            "alarms": {"total": 0, "by_severity": {}},
            "devices": {"total": 0, "by_status": {}},
            "diagnostics": {"total": 0, "by_risk_level": {}},
        }
        
        try:
            # Device stats (fast, from registry)
            if self.device_registry:
                devices = self.device_registry.get_all_devices()
                if site_id:
                    devices = [d for d in devices if d.site_id == site_id]
                
                stats["devices"]["total"] = len(devices)
                from ..core.device_registry import DeviceStatus
                for status in DeviceStatus:
                    count = sum(1 for d in devices if d.status == status)
                    if count > 0:
                        stats["devices"]["by_status"][status.value] = count
            
            # Alarm stats (lightweight query, only count active alarms)
            if self.influx_client:
                try:
                    # Query only recent active alarms for quick stats
                    alarms = self.influx_client.query_alarms(
                        start_time="-24h",  # Last 24 hours
                        limit=1000,  # Limit for performance
                    )
                    
                    if site_id:
                        alarms = [a for a in alarms if a.get("site_id") == site_id]
                    
                    stats["alarms"]["total"] = len(alarms)
                    for alarm in alarms:
                        severity = alarm.get("severity", "Unknown")
                        stats["alarms"]["by_severity"][severity] = stats["alarms"]["by_severity"].get(severity, 0) + 1
                except Exception as e:
                    logger.debug(f"Error getting quick alarm stats: {e}")
            
            # Diagnostic stats (lightweight query)
            if self.influx_client:
                try:
                    diagnostics = self.influx_client.query_diagnostics(
                        start_time="-24h",  # Last 24 hours
                        limit=1000,  # Limit for performance
                    )
                    
                    if site_id:
                        diagnostics = [d for d in diagnostics if d.get("site_id") == site_id]
                    
                    stats["diagnostics"]["total"] = len(diagnostics)
                    for diag in diagnostics:
                        risk_level = diag.get("risk_level", "Unknown")
                        stats["diagnostics"]["by_risk_level"][risk_level] = stats["diagnostics"]["by_risk_level"].get(risk_level, 0) + 1
                except Exception as e:
                    logger.debug(f"Error getting quick diagnostic stats: {e}")
        except Exception as e:
            logger.debug(f"Error getting quick stats: {e}")
        
        return stats

    async def _broadcast_alarm_created(self, alarm, result):
        """Broadcast alarm creation via WebSocket with full data"""
        try:
            from ..agent.dependencies import get_app_state
            from ..agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                site_id = alarm.metadata.get("site_id") if hasattr(alarm, "metadata") and alarm.metadata else None
                
                # Get quick stats to include in broadcast
                stats = await self._get_quick_stats(site_id=site_id)
                
                # Broadcast alarm_created event with full alarm data and stats
                await websocket_manager.broadcast(
                    EventType.ALARM_CREATED,
                    {
                        "alarm": {
                            "alarm_id": alarm.alarm_id,
                            "alarm_type": alarm.alarm_type,
                            "device_id": alarm.device_id,
                            "severity": alarm.severity.value,
                            "message": alarm.message,
                            "timestamp": alarm.timestamp.isoformat() if hasattr(alarm.timestamp, 'isoformat') else str(alarm.timestamp),
                            "site_id": site_id,
                        },
                        "diagnostic": result.get("diagnostic"),
                        "stats": stats,  # Include stats to avoid frontend HTTP request
                    },
                )
                # Also broadcast stats_updated with full stats
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "reason": "alarm_created",
                        "alarm_type": alarm.alarm_type,
                        "site_id": site_id,
                        "stats": stats,  # Include stats to avoid frontend HTTP request
                    },
                )
        except Exception as e:
            logger.debug(f"Error broadcasting alarm creation: {e}")

    async def _broadcast_device_status_changed(
        self, 
        device_id: str, 
        previous_status: DeviceStatus, 
        new_status: DeviceStatus,
        device: RegisteredDevice
    ):
        """Broadcast device status change via WebSocket"""
        try:
            from ..agent.dependencies import get_app_state
            from ..agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager and device:
                await websocket_manager.broadcast(
                    EventType.DEVICE_STATUS_CHANGED,
                    {
                        "device_id": device_id,
                        "previous_status": previous_status.value if previous_status else None,
                        "status": new_status.value,
                        "device": device.to_dict(),
                    },
                )
                # Also broadcast stats update to refresh site statistics
                # Get quick stats to include in broadcast
                stats = await self._get_quick_stats(site_id=device.site_id if hasattr(device, 'site_id') else None)
                
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "device_id": device_id,
                        "status": new_status.value,
                        "stats": stats,  # Include stats to avoid frontend HTTP request
                    },
                )
        except Exception as e:
            logger.debug(f"Error broadcasting device status change: {e}")

    def _create_alarm_from_webhook(self, webhook_data: Dict[str, Any]) -> Alarm:
        """Create Alarm object from webhook data"""
        alarm_id = f"GRAFANA_{webhook_data.get('alarm_type', 'unknown')}_{int(datetime.now(UTC).timestamp())}"

        # Map severity
        severity_str = webhook_data.get("severity", "Warning")
        try:
            severity = AlarmSeverity(severity_str)
        except ValueError:
            severity = AlarmSeverity.WARNING

        # Parse timestamp
        timestamp = webhook_data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(UTC)

        return Alarm(
            alarm_id=alarm_id,
            alarm_type=webhook_data.get("alarm_type", "unknown"),
            severity=severity,
            timestamp=timestamp,
            source=webhook_data.get("source", "grafana"),
            metadata={
                "device_id": webhook_data.get("device_id"),
                "device_type": webhook_data.get("device_type"),
                "site_id": webhook_data.get("site_id"),
                "labels": webhook_data.get("labels", {}),
                "annotations": webhook_data.get("annotations", {}),
                "metric_data": webhook_data.get("metric_data", {}),
            },
        )

    def _create_device_data_from_webhook(
        self, webhook_data: Dict[str, Any]
    ) -> DeviceData:
        """Create DeviceData from webhook data"""
        device_id = webhook_data.get("device_id", "unknown")
        device_type_str = webhook_data.get("device_type", "")
        try:
            device_type = DeviceType(device_type_str.upper())
        except ValueError:
            device_type = DeviceType.OTHER

        timestamp = webhook_data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(UTC)

        # Extract metric data
        metric_data = webhook_data.get("metric_data", {})
        labels = webhook_data.get("labels", {})

        return DeviceData(
            device_id=device_id,
            device_type=device_type,
            timestamp=timestamp,
            source=webhook_data.get("source", "grafana"),
            site_id=webhook_data.get("site_id") or labels.get("site_id"),
            site_name=webhook_data.get("site_name") or labels.get("site_name"),
            data=metric_data,
            metadata={
                "labels": labels,
                "annotations": webhook_data.get("annotations", {}),
            },
        )
