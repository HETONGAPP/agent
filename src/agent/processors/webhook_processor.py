"""
Webhook processing logic
"""
import logging
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from ...models.alarm import Alarm, AlarmSeverity
from ...models.device_data import DeviceData, DeviceType
from ...rule_engine import RuleEngine
from ...core.device_registry import DeviceRegistry, DeviceStatus
from ...storage.influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Handles webhook alarm processing from Grafana"""
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        influx_client: Optional[InfluxDBClient] = None,
        check_device_status: bool = True,
        reject_inactive_devices: bool = False,
    ):
        """
        Initialize webhook processor
        
        Args:
            rule_engine: Rule engine instance
            influx_client: Optional InfluxDB client
            check_device_status: Whether to check device status
            reject_inactive_devices: Whether to reject inactive devices
        """
        self.rule_engine = rule_engine
        self.influx_client = influx_client
        self.check_device_status = check_device_status
        self.reject_inactive_devices = reject_inactive_devices
    
    async def process_webhook_alarm(
        self,
        webhook_data: Dict[str, Any],
        device_data: Optional[DeviceData] = None,
        alarm_processor=None,  # Will be injected
    ) -> Dict[str, Any]:
        """
        Process alarm from Grafana webhook
        
        Args:
            webhook_data: Parsed webhook data
            device_data: Optional device data
            alarm_processor: Alarm processor instance
            
        Returns:
            Processing result dictionary
        """
        try:
            # Create Alarm and DeviceData from webhook
            alarm = self._create_alarm_from_webhook(webhook_data)
            if device_data is None:
                device_data = self._create_device_data_from_webhook(webhook_data)
            
            # Check device status
            if self.check_device_status:
                status_result = await self._check_device_status(device_data)
                if status_result:
                    return status_result
            
            # Evaluate rules
            alarms = self.rule_engine.evaluate(device_data)
            
            # If no rules matched, use the webhook alarm
            if not alarms:
                alarms = [alarm]
            
            # Process each alarm
            results = []
            for alarm in alarms:
                result = await alarm_processor.process_alarm(alarm, device_data, webhook_data=webhook_data)
                results.append(result)
            
            # Flush InfluxDB buffer
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
    ) -> Optional[Dict[str, Any]]:
        """Check device status before processing"""
        from ...agent.dependencies import get_device_registry
        device_registry = get_device_registry()
        registered_device = device_registry.get_device(device_data.device_id)
        
        if not registered_device:
            logger.warning(
                f"✗ Rejecting webhook data from unregistered device {device_data.device_id}"
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
                logger.warning(
                    f"✗ Rejecting webhook data from INACTIVE device {device_data.device_id}"
                )
                return {
                    "status": "rejected",
                    "message": f"Device {device_data.device_id} is INACTIVE. Webhook data rejected.",
                    "device_id": device_data.device_id,
                    "device_status": "INACTIVE",
                    "alarms_processed": 0,
                }
            else:
                # Auto-recover device
                registered_device.status = DeviceStatus.ACTIVE
                device_registry.mark_device_seen(device_data.device_id)
                logger.info(f"✓ Device {device_data.device_id} recovered")
        elif registered_device.status == DeviceStatus.ACTIVE:
            device_registry.mark_device_seen(device_data.device_id)
        
        return None
    
    def _create_alarm_from_webhook(self, webhook_data: Dict[str, Any]) -> Alarm:
        """Create Alarm object from webhook data"""
        alarm_id = f"GRAFANA_{webhook_data.get('alarm_type', 'unknown')}_{int(datetime.now(UTC).timestamp())}"
        
        severity_str = webhook_data.get("severity", "Warning")
        try:
            severity = AlarmSeverity(severity_str)
        except ValueError:
            severity = AlarmSeverity.WARNING
        
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
    
    def _create_device_data_from_webhook(self, webhook_data: Dict[str, Any]) -> DeviceData:
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
