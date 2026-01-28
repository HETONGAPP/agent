"""
Agent Service - Main processing service
Integrates rule engine, LLM diagnostic, and Grafana annotation
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..core.data_flow_tracker import DataFlowTracker
from ..core.device_discovery import DeviceDiscoveryService
from ..core.device_registry import DeviceRegistry, DeviceStatus, RegisteredDevice
from ..core.integration import DeviceIntegration
from ..email import EmailService
from ..grafana import AnnotationService, GrafanaClient
from ..llm_diagnostic import LLMDiagnosticService
from ..models.alarm import Alarm
from ..models.device_data import DeviceData, DeviceType
from ..rule_engine import RuleEngine
from ..storage.influxdb_client import InfluxDBClient
from ..storage.site_container import SiteContainerManager
from .processors import (
    AlarmProcessor,
    DeviceProcessor,
    WebhookProcessor,
    BroadcastProcessor,
)
from .utils.deduplication import DataDeduplicator

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
            integrations: Optional dictionary of device integrations
            device_discovery: Optional device discovery service
            flow_tracker: Optional data flow tracker
            check_device_status: If True, check device status before processing data
            auto_register_devices: If True, automatically register unknown devices from MQTT
            reject_inactive_devices: If True, reject data from INACTIVE devices
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
        self.check_device_status = check_device_status
        self.auto_register_devices = auto_register_devices
        self.reject_inactive_devices = reject_inactive_devices
        
        # Auto-diagnostic configuration: disabled by default
        self._auto_diagnostic_enabled = False
        
        # Initialize site container manager if InfluxDB client is available
        self.container_manager = None
        self.use_containers = True
        if influx_client:
            try:
                self.container_manager = SiteContainerManager(influx_client)
                logger.info("✓ Site container manager initialized (container mode enabled)")
            except Exception as e:
                logger.warning(f"⚠ Failed to initialize site container manager: {e}")
                self.use_containers = False
        
        # Initialize data deduplicator
        self.deduplicator = DataDeduplicator()
        
        # Initialize processors
        self.alarm_processor = AlarmProcessor(
            llm_diagnostic_service=llm_diagnostic_service,
            annotation_service=annotation_service,
            email_service=email_service,
            influx_client=influx_client,
            container_manager=self.container_manager,
            use_containers=self.use_containers,
            flow_tracker=flow_tracker,
            auto_diagnostic_enabled=self._auto_diagnostic_enabled,
        )
        
        self.device_processor = DeviceProcessor(
            rule_engine=rule_engine,
            influx_client=influx_client,
            container_manager=self.container_manager,
            use_containers=self.use_containers,
            flow_tracker=flow_tracker,
            check_device_status=check_device_status,
            reject_inactive_devices=reject_inactive_devices,
            deduplicator=self.deduplicator,
        )
        
        self.webhook_processor = WebhookProcessor(
            rule_engine=rule_engine,
            influx_client=influx_client,
            check_device_status=check_device_status,
            reject_inactive_devices=reject_inactive_devices,
        )
        
        self.broadcast_processor = BroadcastProcessor(
            influx_client=influx_client,
        )
        
        # Periodic flush task for InfluxDB buffer
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_interval: float = 10.0
        self._running: bool = False
        
        # Set up device discovery callbacks
        if self.device_discovery:
            self.device_discovery.on_device_discovered(self._on_device_discovered)
            self.device_discovery.on_device_removed(self._on_device_removed)
    
    def _on_device_discovered(self, device: RegisteredDevice):
        """Callback when a new device is discovered"""
        logger.info(
            f"New device discovered: {device.device_id} (type={device.device_type.value})"
        )
    
    def _on_device_removed(self, device: RegisteredDevice):
        """Callback when a device is removed"""
        logger.info(
            f"Device removed: {device.device_id} (type={device.device_type.value})"
        )
        # Clean up deduplication keys for this device
        self.deduplicator.remove_device_keys(device.device_id)
    
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
        return await self.webhook_processor.process_webhook_alarm(
            webhook_data=webhook_data,
            device_data=device_data,
            alarm_processor=self.alarm_processor,
        )
    
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
            
            # Process device data using DeviceProcessor
            return await self.device_processor.process_device_data(
                device_data=device_data,
                history=history,
                alarm_processor=self.alarm_processor,
                broadcast_processor=self.broadcast_processor,
            )
        except Exception as e:
            logger.error(f"Failed to process device data: {e}", exc_info=True)
            if self.influx_client:
                try:
                    self.influx_client.flush()
                except Exception:
                    pass
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
        """Process a single alarm (delegates to AlarmProcessor)"""
        result = await self.alarm_processor.process_alarm(
            alarm=alarm,
            device_data=device_data,
            webhook_data=webhook_data,
            rule=rule,
        )
        
        # Broadcast alarm creation
        await self.broadcast_processor.broadcast_alarm_created(alarm, result)
        
        return result
    
    async def _get_quick_stats(self, site_id: Optional[str] = None) -> Dict[str, Any]:
        """Get quick statistics (delegates to BroadcastProcessor)"""
        return await self.broadcast_processor._get_quick_stats(site_id=site_id)
    
    async def _broadcast_alarm_created(self, alarm, result):
        """Broadcast alarm creation (delegates to BroadcastProcessor)"""
        await self.broadcast_processor.broadcast_alarm_created(alarm, result)
    
    async def _broadcast_device_status_changed(
        self,
        device_id: str,
        previous_status: DeviceStatus,
        new_status: DeviceStatus,
        device: RegisteredDevice,
    ):
        """Broadcast device status change (delegates to BroadcastProcessor)"""
        await self.broadcast_processor.broadcast_device_status_changed(
            device_id, previous_status, new_status, device
        )
    
    def _create_alarm_from_webhook(self, webhook_data: Dict[str, Any]) -> Alarm:
        """Create Alarm from webhook data (delegates to WebhookProcessor)"""
        return self.webhook_processor._create_alarm_from_webhook(webhook_data)
    
    def _create_device_data_from_webhook(self, webhook_data: Dict[str, Any]) -> DeviceData:
        """Create DeviceData from webhook data (delegates to WebhookProcessor)"""
        return self.webhook_processor._create_device_data_from_webhook(webhook_data)
