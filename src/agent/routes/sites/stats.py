"""
Site statistics and operations routes
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from ....core import DeviceRegistry
from ....storage.influxdb_client import InfluxDBClient
from ...service import AgentService
from ...site_manager import SiteManager
from ...dependencies import (
    get_site_manager,
    get_device_registry,
    get_influx_client,
    get_agent_service,
    get_app_state,
)
from ...rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    """Register site statistics and operations routes"""

    @app.get("/api/v1/sites/{site_id}/stats")
    async def get_site_stats(
        site_id: str,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get statistics for a specific site"""
        if not site_manager or not site_manager.site_exists(site_id):
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Site not found: {site_id}",
                },
            )
        
        try:
            stats = {
                "site_id": site_id,
                "devices": {
                    "total": 0,
                    "by_status": {},
                    "by_type": {},
                },
                "alarms": {
                    "total": 0,
                    "by_severity": {},
                },
            }
            
            # Get device stats
            if device_registry:
                inactive_timeout_seconds = 30
                now = datetime.now(timezone.utc)
                
                all_devices = device_registry.get_all_devices()
                site_devices = []
                for device in all_devices:
                    device_dict = device.to_dict()
                    if device_dict.get("metadata", {}).get("site_id") == site_id:
                        site_devices.append(device)
                
                stats["devices"]["total"] = len(site_devices)
                for device in site_devices:
                    device_status = device.status.value
                    last_seen = device.last_seen
                    
                    if device_status == "active" and last_seen:
                        try:
                            if isinstance(last_seen, str):
                                if last_seen.endswith("Z"):
                                    last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                                else:
                                    last_seen_dt = datetime.fromisoformat(last_seen)
                                if last_seen_dt.tzinfo is None:
                                    last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                            else:
                                last_seen_dt = last_seen
                                if last_seen_dt.tzinfo is None:
                                    last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                            
                            time_since_last_seen = (now - last_seen_dt).total_seconds()
                            if time_since_last_seen > inactive_timeout_seconds:
                                device_status = "inactive"
                        except Exception as e:
                            logger.warning(
                                f"[get_site_stats] Error parsing last_seen for device {device.device_id}: {e}",
                                exc_info=True
                            )
                    
                    stats["devices"]["by_status"][device_status] = stats["devices"]["by_status"].get(device_status, 0) + 1
                    device_type = device.device_type.value
                    stats["devices"]["by_type"][device_type] = stats["devices"]["by_type"].get(device_type, 0) + 1
            
            # Get alarm stats from site container or InfluxDB
            if influx_client:
                try:
                    if agent_service and agent_service.container_manager:
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            alarms = container.query_alarms(limit=10000)
                        else:
                            alarms = []
                    else:
                        alarms = influx_client.query_alarms(site_id=site_id, limit=1000)
                    
                    stats["alarms"]["total"] = len(alarms)
                    for alarm in alarms:
                        severity = alarm.get("severity", "Unknown")
                        stats["alarms"]["by_severity"][severity] = stats["alarms"]["by_severity"].get(severity, 0) + 1
                except Exception as e:
                    logger.warning(f"Failed to query alarm stats for site {site_id}: {e}")
            
            return {
                "status": "success",
                "data": stats,
            }
        except Exception as e:
            logger.error(f"Error getting site stats: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.post("/api/v1/sites/{site_id}/reload")
    async def reload_site(
        site_id: str,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Reload site configuration"""
        if not site_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Site manager not initialized",
                },
            )
        
        try:
            if not site_manager.site_exists(site_id):
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Site not found: {site_id}",
                    },
                )
            
            site_manager.reload_site(site_id)
            
            # Also reload in rule engine if available
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            return {
                "status": "success",
                "message": f"Site {site_id} configuration reloaded",
            }
        except Exception as e:
            logger.error(f"Error reloading site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
