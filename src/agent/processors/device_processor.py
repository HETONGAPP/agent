"""
Device data processing logic
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...models.device_data import DeviceData, DeviceType
from ...models.alarm import Alarm
from ...rule_engine import RuleEngine
from ...storage.influxdb_client import InfluxDBClient
from ...storage.site_container import SiteContainerManager
from ...core.device_registry import DeviceRegistry, DeviceStatus
from ...core.data_flow_tracker import DataFlowTracker
from ..utils.deduplication import DataDeduplicator

logger = logging.getLogger(__name__)


class DeviceProcessor:
    """Handles device data processing including storage, rule evaluation, and alarm generation"""
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        influx_client: Optional[InfluxDBClient] = None,
        container_manager: Optional[SiteContainerManager] = None,
        use_containers: bool = True,
        flow_tracker: Optional[DataFlowTracker] = None,
        check_device_status: bool = True,
        reject_inactive_devices: bool = False,
        deduplicator: Optional[DataDeduplicator] = None,
    ):
        """
        Initialize device processor
        
        Args:
            rule_engine: Rule engine instance
            influx_client: Optional InfluxDB client
            container_manager: Optional site container manager
            use_containers: Whether to use site containers
            flow_tracker: Optional data flow tracker
            check_device_status: Whether to check device status
            reject_inactive_devices: Whether to reject inactive devices
            deduplicator: Optional data deduplicator
        """
        self.rule_engine = rule_engine
        self.influx_client = influx_client
        self.container_manager = container_manager
        self.use_containers = use_containers
        self.flow_tracker = flow_tracker
        self.check_device_status = check_device_status
        self.reject_inactive_devices = reject_inactive_devices
        self.deduplicator = deduplicator or DataDeduplicator()
    
    async def process_device_data(
        self,
        device_data: DeviceData,
        history: Optional[List[DeviceData]] = None,
        alarm_processor=None,  # Will be injected
        broadcast_processor=None,  # Will be injected
    ) -> Dict[str, Any]:
        """
        Process device data
        
        Args:
            device_data: Device data to process
            history: Optional historical data
            alarm_processor: Alarm processor instance
            broadcast_processor: Broadcast processor instance
            
        Returns:
            Processing result dictionary
        """
        try:
            # Track input stage
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
            
            # Check for duplicate data
            if self.deduplicator.is_duplicate(device_data):
                logger.debug(
                    f"⏭ [DeviceProcessor] Skipping duplicate data: "
                    f"device_id={device_data.device_id}, timestamp={device_data.timestamp}"
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
            
            # Check and update device status
            status_result = await self._check_device_status(device_data, broadcast_processor)
            if status_result:
                return status_result
            
            # Store device data
            await self._store_device_data(device_data)
            
            # Evaluate rules
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="rule_evaluation",
                    data_id=device_data.device_id,
                )
            
            alarms = self.rule_engine.evaluate(device_data, history)
            logger.info(
                f"[DeviceProcessor] Rule evaluation for {device_data.device_id}: "
                f"Generated {len(alarms)} alarms"
            )
            
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="rule_evaluation_complete",
                    data_id=device_data.device_id,
                    metadata={"alarms_count": len(alarms)},
                    status="success" if alarms else "no_alarms",
                )
            
            # Process alarms
            if alarms:
                results = await self._process_alarms(
                    alarms, device_data, alarm_processor, broadcast_processor
                )
            else:
                results = []
            
            # Broadcast stats update
            if broadcast_processor:
                await broadcast_processor.broadcast_stats_updated(
                    site_id=device_data.site_id,
                    device_id=device_data.device_id,
                    device_type=device_data.device_type.value,
                )
            
            # Flush InfluxDB buffer
            if self.influx_client:
                try:
                    self.influx_client.flush()
                except Exception as e:
                    logger.error(f"Failed to flush InfluxDB buffer: {e}", exc_info=True)
            
            return {
                "status": "success",
                "alarms_processed": len(results),
                "results": results,
                "data_stored": True,
            }
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
    
    async def _check_device_status(
        self,
        device_data: DeviceData,
        broadcast_processor,
    ) -> Optional[Dict[str, Any]]:
        """Check and update device status"""
        if not self.check_device_status:
            return None
        
        from ...agent.dependencies import get_device_registry
        device_registry = get_device_registry()
        registered_device = device_registry.get_device(device_data.device_id)
        
        if registered_device:
            return await self._handle_registered_device(
                registered_device, device_data, device_registry, broadcast_processor
            )
        else:
            return await self._handle_unregistered_device(
                device_data, device_registry, broadcast_processor
            )
    
    async def _handle_registered_device(
        self,
        registered_device,
        device_data: DeviceData,
        device_registry: DeviceRegistry,
        broadcast_processor,
    ) -> Optional[Dict[str, Any]]:
        """Handle registered device status"""
        if registered_device.status == DeviceStatus.INACTIVE:
            if self.reject_inactive_devices:
                logger.warning(
                    f"✗ Rejecting data from INACTIVE device {device_data.device_id}"
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
                # Auto-recover device
                previous_status = registered_device.status
                registered_device.status = DeviceStatus.ACTIVE
                device_registry.mark_device_seen(device_data.device_id)
                logger.info(f"✓ Device {device_data.device_id} recovered")
                
                if broadcast_processor:
                    await broadcast_processor.broadcast_device_status_changed(
                        device_data.device_id, previous_status, DeviceStatus.ACTIVE, registered_device
                    )
                
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="device_recovery",
                        data_id=device_data.device_id,
                        metadata={"previous_status": "INACTIVE"},
                        status="recovered",
                    )
        elif registered_device.status == DeviceStatus.ACTIVE:
            device_registry.mark_device_seen(device_data.device_id)
        elif registered_device.status == DeviceStatus.REGISTERED:
            previous_status = registered_device.status
            device_registry.mark_device_seen(device_data.device_id)
            updated_device = device_registry.get_device(device_data.device_id)
            if updated_device and updated_device.status == DeviceStatus.ACTIVE:
                if broadcast_processor:
                    await broadcast_processor.broadcast_device_status_changed(
                        device_data.device_id, previous_status, DeviceStatus.ACTIVE, updated_device
                    )
        
        return None
    
    async def _handle_unregistered_device(
        self,
        device_data: DeviceData,
        device_registry: DeviceRegistry,
        broadcast_processor,
    ) -> Optional[Dict[str, Any]]:
        """Handle unregistered device - auto-register"""
        logger.info(
            f"🔄 Auto-registering device {device_data.device_id} "
            f"(type={device_data.device_type.value}, site_id={device_data.site_id})"
        )
        
        metadata = {
            "site_id": device_data.site_id,
            "source": device_data.source or "mqtt",
            "registered_via": "auto_mqtt",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        if device_data.site_name:
            metadata["site_name"] = device_data.site_name
        
        try:
            registered_device = device_registry.register_device(
                device_id=device_data.device_id,
                device_type=device_data.device_type,
                integration_name="mqtt",
                metadata=metadata,
            )
            
            if registered_device.status == DeviceStatus.UNREGISTERED:
                logger.warning(f"✗ Auto-registration rejected for device {device_data.device_id}")
                if self.flow_tracker:
                    self.flow_tracker.track(
                        stage="device_status_check",
                        data_id=device_data.device_id,
                        metadata={"status": "unregistered", "action": "rejected"},
                        status="rejected",
                    )
                return {
                    "status": "rejected",
                    "message": f"Device {device_data.device_id} auto-registration rejected.",
                    "device_id": device_data.device_id,
                    "device_status": "unregistered",
                    "alarms_processed": 0,
                    "data_stored": False,
                }
            
            device_registry.mark_device_seen(device_data.device_id)
            logger.info(f"✓ Device {device_data.device_id} auto-registered successfully")
            
            # Broadcast device added event
            from ...agent.dependencies import get_app_state
            from ...agent.websocket_manager import EventType
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
            
            # Auto-create rules
            if device_data.site_id:
                try:
                    from ...agent.dependencies import get_site_manager
                    site_manager = get_site_manager()
                    if site_manager:
                        rules_created = site_manager.create_device_rules(
                            device_id=device_data.device_id,
                            device_type=device_data.device_type.value,
                            site_id=device_data.site_id
                        )
                        logger.info(f"Auto-created {rules_created} rules for device {device_data.device_id}")
                except Exception as e:
                    logger.warning(f"Failed to auto-create rules for device {device_data.device_id}: {e}")
        except Exception as e:
            logger.error(f"✗ Failed to auto-register device {device_data.device_id}: {e}", exc_info=True)
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="device_auto_registration",
                    data_id=device_data.device_id,
                    metadata={"error": str(e)},
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
        
        return None
    
    async def _store_device_data(self, device_data: DeviceData):
        """Store device data to InfluxDB"""
        if self.use_containers and self.container_manager and device_data.site_id:
            try:
                container = self.container_manager.get_container(device_data.site_id, auto_create=True)
                container.write_device_data(device_data, flush=False)
                logger.debug(
                    f"✓ Stored {device_data.device_type.value} data to site container: "
                    f"site_id={device_data.site_id}, device_id={device_data.device_id}"
                )
            except Exception as e:
                logger.error(f"✗ Failed to store device data to site container: {e}", exc_info=True)
        elif self.influx_client:
            try:
                self.influx_client.write_device_data(device_data, flush=False)
                logger.debug(f"✓ Stored {device_data.device_type.value} data to InfluxDB: device_id={device_data.device_id}")
            except Exception as e:
                logger.error(f"✗ Failed to store device data to InfluxDB: {e}", exc_info=True)
        else:
            logger.warning("⚠ InfluxDB client not available, cannot store data")
    
    async def _process_alarms(
        self,
        alarms: List[Alarm],
        device_data: DeviceData,
        alarm_processor,
        broadcast_processor,
    ) -> List[Dict[str, Any]]:
        """Process all alarms"""
        async def process_single_alarm(alarm: Alarm) -> Dict[str, Any]:
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="alarm_processing",
                    data_id=device_data.device_id,
                    metadata={"alarm_type": alarm.alarm_type, "severity": alarm.severity.value},
                )
            
            rule = self.rule_engine.get_rule(alarm.metadata.get("rule_id", ""))
            result = await alarm_processor.process_alarm(alarm, device_data, rule=rule)
            
            if broadcast_processor:
                await broadcast_processor.broadcast_alarm_created(alarm, result)
            
            if self.flow_tracker:
                self.flow_tracker.track(
                    stage="alarm_processing_complete",
                    data_id=device_data.device_id,
                    metadata={"alarm_type": alarm.alarm_type},
                    status=result.get("status", "success"),
                )
            
            return result
        
        if len(alarms) > 1:
            logger.debug(f"Processing {len(alarms)} alarms in parallel")
            tasks = [process_single_alarm(alarm) for alarm in alarms]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing alarm {i}: {result}", exc_info=True)
                    processed_results.append({
                        "status": "error",
                        "error": str(result),
                        "alarm": alarms[i].to_dict() if i < len(alarms) else None,
                    })
                else:
                    processed_results.append(result)
            return processed_results
        else:
            return [await process_single_alarm(alarms[0])]
