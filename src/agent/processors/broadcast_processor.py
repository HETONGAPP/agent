"""
Event broadcasting logic
"""
import logging
from typing import Any, Dict, Optional

from ...core.device_registry import DeviceStatus, RegisteredDevice
from ...storage.influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


class BroadcastProcessor:
    """Handles WebSocket event broadcasting"""
    
    def __init__(
        self,
        influx_client: Optional[InfluxDBClient] = None,
    ):
        """
        Initialize broadcast processor
        
        Args:
            influx_client: Optional InfluxDB client for stats queries
        """
        self.influx_client = influx_client
    
    async def broadcast_alarm_created(
        self,
        alarm,
        result: Dict[str, Any],
    ):
        """Broadcast alarm creation via WebSocket"""
        try:
            from ...agent.dependencies import get_app_state
            from ...agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if not websocket_manager:
                return
            
            site_id = alarm.metadata.get("site_id") if hasattr(alarm, "metadata") and alarm.metadata else None
            
            # Get quick stats to include in broadcast
            stats = await self._get_quick_stats(site_id=site_id)
            
            # Broadcast alarm_created event
            await websocket_manager.broadcast(
                EventType.ALARM_CREATED,
                {
                    "alarm": {
                        "alarm_id": alarm.alarm_id,
                        "alarm_type": alarm.alarm_type,
                        "device_id": alarm.metadata.get("device_id") if alarm.metadata else None,
                        "severity": alarm.severity.value,
                        "message": alarm.metadata.get("rule_name", alarm.alarm_type) if alarm.metadata else alarm.alarm_type,
                        "timestamp": alarm.timestamp.isoformat() if hasattr(alarm.timestamp, 'isoformat') else str(alarm.timestamp),
                        "site_id": site_id,
                    },
                    "site_id": site_id,
                    "diagnostic": result.get("diagnostic"),
                    "stats": stats,
                },
            )
            
            # Also broadcast stats_updated
            await websocket_manager.broadcast(
                EventType.STATS_UPDATED,
                {
                    "reason": "alarm_created",
                    "alarm_type": alarm.alarm_type,
                    "site_id": site_id,
                    "stats": stats,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting alarm creation: {e}")
    
    async def broadcast_device_status_changed(
        self,
        device_id: str,
        previous_status: DeviceStatus,
        new_status: DeviceStatus,
        device: RegisteredDevice,
    ):
        """Broadcast device status change via WebSocket"""
        try:
            from ...agent.dependencies import get_app_state
            from ...agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if not websocket_manager or not device:
                return
            
            await websocket_manager.broadcast(
                EventType.DEVICE_STATUS_CHANGED,
                {
                    "device_id": device_id,
                    "previous_status": previous_status.value if previous_status else None,
                    "status": new_status.value,
                    "device": device.to_dict(),
                },
            )
            
            # Also broadcast stats update
            site_id = device.site_id if hasattr(device, 'site_id') else None
            stats = await self._get_quick_stats(site_id=site_id)
            
            await websocket_manager.broadcast(
                EventType.STATS_UPDATED,
                {
                    "device_id": device_id,
                    "status": new_status.value,
                    "stats": stats,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting device status change: {e}")
    
    async def broadcast_stats_updated(
        self,
        site_id: Optional[str] = None,
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
    ):
        """Broadcast stats update via WebSocket"""
        try:
            from ...agent.dependencies import get_app_state
            from ...agent.websocket_manager import EventType
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if not websocket_manager:
                return
            
            stats = await self._get_quick_stats(site_id=site_id)
            
            await websocket_manager.broadcast(
                EventType.STATS_UPDATED,
                {
                    "device_id": device_id,
                    "site_id": site_id,
                    "device_type": device_type,
                    "stats": stats,
                },
            )
        except Exception as e:
            logger.debug(f"Error broadcasting stats update: {e}")
    
    async def _get_quick_stats(self, site_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get quick statistics for WebSocket broadcast
        
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
            from ...agent.dependencies import get_device_registry
            device_registry = get_device_registry()
            if device_registry:
                devices = device_registry.get_all_devices()
                if site_id:
                    devices = [
                        d for d in devices 
                        if (hasattr(d, 'site_id') and d.site_id == site_id) or not hasattr(d, 'site_id')
                    ]
                
                stats["devices"]["total"] = len(devices)
                for status in DeviceStatus:
                    count = sum(1 for d in devices if d.status == status)
                    if count > 0:
                        stats["devices"]["by_status"][status.value] = count
            
            # Alarm stats (lightweight query)
            if self.influx_client:
                try:
                    alarms = self.influx_client.query_alarms(start_time="-24h", limit=1000)
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
                    diagnostics = self.influx_client.query_diagnostics(start_time="-24h", limit=1000)
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
