"""
Alarm processing logic
"""
import asyncio
import logging
from typing import Any, Dict, Optional

from ...models.alarm import Alarm
from ...models.device_data import DeviceData
from ...models.diagnostic import DiagnosticReport
from ...llm_diagnostic import LLMDiagnosticService
from ...grafana import AnnotationService
from ...email import EmailService
from ...storage.influxdb_client import InfluxDBClient
from ...storage.site_container import SiteContainerManager
from ...core.data_flow_tracker import DataFlowTracker
from ...core.event_bus import get_event_bus, EventType as EventBusType

logger = logging.getLogger(__name__)


class AlarmProcessor:
    """Handles alarm processing including diagnostics, storage, and notifications"""
    
    def __init__(
        self,
        llm_diagnostic_service: Optional[LLMDiagnosticService] = None,
        annotation_service: Optional[AnnotationService] = None,
        email_service: Optional[EmailService] = None,
        influx_client: Optional[InfluxDBClient] = None,
        container_manager: Optional[SiteContainerManager] = None,
        use_containers: bool = True,
        flow_tracker: Optional[DataFlowTracker] = None,
        auto_diagnostic_enabled: bool = False,
    ):
        """
        Initialize alarm processor
        
        Args:
            llm_diagnostic_service: Optional LLM diagnostic service
            annotation_service: Optional annotation service
            email_service: Optional email service
            influx_client: Optional InfluxDB client
            container_manager: Optional site container manager
            use_containers: Whether to use site containers
            flow_tracker: Optional data flow tracker
            auto_diagnostic_enabled: Whether auto-diagnostic is enabled
        """
        self.llm_diagnostic_service = llm_diagnostic_service
        self.annotation_service = annotation_service
        self.email_service = email_service
        self.influx_client = influx_client
        self.container_manager = container_manager
        self.use_containers = use_containers
        self.flow_tracker = flow_tracker
        self.auto_diagnostic_enabled = auto_diagnostic_enabled
    
    async def process_alarm(
        self,
        alarm: Alarm,
        device_data: DeviceData,
        webhook_data: Optional[Dict[str, Any]] = None,
        rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a single alarm
        
        Args:
            alarm: Alarm to process
            device_data: Associated device data
            webhook_data: Optional webhook data
            rule: Optional rule that triggered the alarm
            
        Returns:
            Processing result dictionary
        """
        result = {
            "alarm": alarm.to_dict(),
            "diagnostic": None,
            "annotation": None,
            "stored": False,
        }
        
        # Generate LLM diagnostic if enabled
        if self.llm_diagnostic_service and self.auto_diagnostic_enabled:
            result = await self._generate_diagnostic(alarm, device_data, rule, webhook_data, result)
        else:
            logger.debug(f"Auto-diagnostic disabled for alarm {alarm.alarm_id}. Use manual trigger API to generate diagnostic.")
        
        # Store alarm and diagnostic
        await self._store_alarm(alarm, device_data, result)
        
        # Publish event via event bus
        await self._publish_event(alarm, result)
        
        # Send email if available
        if self.email_service and result["diagnostic"]:
            await self._send_email(alarm, device_data, result)
        
        return result
    
    async def _generate_diagnostic(
        self,
        alarm: Alarm,
        device_data: DeviceData,
        rule: Optional[Dict[str, Any]],
        webhook_data: Optional[Dict[str, Any]],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate LLM diagnostic for alarm"""
        if self.flow_tracker:
            self.flow_tracker.track(
                stage="llm_diagnostic",
                data_id=device_data.device_id,
                metadata={"alarm_type": alarm.alarm_type},
            )
        
        try:
            diagnostic_report = await self.llm_diagnostic_service.generate_diagnostic(
                alarm=alarm,
                device_data=device_data,
                rule=rule,
            )
            result["diagnostic"] = diagnostic_report.to_dict()
            
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="llm_diagnostic_complete",
                    data_id=device_data.device_id,
                    metadata={
                        "alarm_type": alarm.alarm_type,
                        "risk_level": diagnostic_report.risk_level,
                    },
                )
            
            # Create Grafana annotation if available
            if self.annotation_service:
                try:
                    annotation = await self.annotation_service.create_diagnostic_annotation_async(
                        alarm=alarm,
                        diagnostic_report=diagnostic_report,
                        dashboard_id=webhook_data.get("dashboard_id") if webhook_data else None,
                        panel_id=webhook_data.get("panel_id") if webhook_data else None,
                    )
                    result["annotation"] = annotation
                except Exception as e:
                    logger.warning(f"Failed to create annotation: {e}", exc_info=True)
                    result["annotation_error"] = str(e)
        except Exception as e:
            logger.error(f"Failed to generate diagnostic: {e}", exc_info=True)
            result["diagnostic_error"] = str(e)
        
        return result
    
    async def _store_alarm(
        self,
        alarm: Alarm,
        device_data: DeviceData,
        result: Dict[str, Any],
    ):
        """Store alarm and diagnostic to InfluxDB"""
        if not self.influx_client:
            result["stored"] = False
            result["storage_error"] = "No InfluxDB client available"
            return
        
        # Get site_id from device registration or device_data
        site_id = self._get_site_id(device_data)
        
        try:
            # Use site container if available
            if self.use_containers and self.container_manager and site_id:
                await self._store_to_container(alarm, result, site_id)
            elif self.influx_client:
                await self._store_to_influxdb(alarm, result, site_id)
            else:
                result["stored"] = False
                result["storage_error"] = "No storage available"
        except Exception as e:
            logger.warning(f"Failed to store alarm to InfluxDB (first attempt): {e}")
            result["stored"] = False
            result["storage_error"] = str(e)
            
            # Retry with exponential backoff
            await self._retry_storage(alarm, result, site_id)
    
    def _get_site_id(self, device_data: DeviceData) -> Optional[str]:
        """Get site_id from device registration or device_data"""
        from ...agent.dependencies import get_device_registry
        
        device_registry = get_device_registry()
        registered_device = device_registry.get_device(device_data.device_id)
        if registered_device and registered_device.metadata:
            return registered_device.metadata.get("site_id")
        return device_data.site_id
    
    async def _store_to_container(
        self,
        alarm: Alarm,
        result: Dict[str, Any],
        site_id: str,
    ):
        """Store alarm to site container"""
        try:
            container = self.container_manager.get_container(site_id, auto_create=True)
            container.write_alarm(alarm, flush=True)
            
            if result["diagnostic"]:
                diagnostic_dict = result["diagnostic"].copy()
                if "metadata" not in diagnostic_dict:
                    diagnostic_dict["metadata"] = {}
                
                # Copy metadata from alarm
                if alarm.metadata.get("device_id"):
                    diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                if alarm.metadata.get("device_type"):
                    diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                
                container.write_diagnostic(alarm.alarm_id, diagnostic_dict)
            
            result["stored"] = True
            logger.debug(f"✓ Stored alarm to site container: site_id={site_id}, alarm_id={alarm.alarm_id}")
        except Exception as e:
            raise e
    
    async def _store_to_influxdb(
        self,
        alarm: Alarm,
        result: Dict[str, Any],
        site_id: Optional[str],
    ):
        """Store alarm to InfluxDB (legacy mode)"""
        self.influx_client.write_alarm(alarm, flush=True, site_id=site_id)
        
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
    
    async def _retry_storage(
        self,
        alarm: Alarm,
        result: Dict[str, Any],
        site_id: Optional[str],
    ):
        """Retry storage with exponential backoff"""
        max_retries = 2
        retry_delay = 0.5
        
        for retry in range(max_retries):
            try:
                await asyncio.sleep(retry_delay)
                logger.info(f"Retrying alarm storage (attempt {retry + 2}/{max_retries + 1})")
                
                if self.use_containers and self.container_manager and site_id:
                    await self._store_to_container(alarm, result, site_id)
                elif self.influx_client:
                    await self._store_to_influxdb(alarm, result, site_id)
                
                result["storage_error"] = None
                logger.info(f"✓ Alarm storage succeeded on retry {retry + 2}")
                break
            except Exception as retry_error:
                logger.warning(f"Alarm storage retry {retry + 2} failed: {retry_error}")
                retry_delay *= 2
                if retry == max_retries - 1:
                    logger.error(f"✗ Alarm storage failed after {max_retries + 1} attempts: {retry_error}")
                    result["storage_error"] = f"Failed after {max_retries + 1} attempts: {str(retry_error)}"
    
    async def _publish_event(self, alarm: Alarm, result: Dict[str, Any]):
        """Publish alarm event via event bus"""
        try:
            from ...agent.dependencies import get_app_state
            
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
    
    async def _send_email(
        self,
        alarm: Alarm,
        device_data: DeviceData,
        result: Dict[str, Any],
    ):
        """Send email notification"""
        if not result["diagnostic"]:
            return
        
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
