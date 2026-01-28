"""
Site alarms routes
"""
import logging
from typing import Optional
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from ....storage.influxdb_client import InfluxDBClient
from ...service import AgentService
from ...site_manager import SiteManager
from ...dependencies import (
    get_site_manager,
    get_influx_client,
    get_agent_service,
)
from ...rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    """Register site alarms routes"""

    @app.get("/api/v1/sites/{site_id}/alarms")
    async def get_site_alarms(
        site_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get alarms for a specific site"""
        if not site_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Site manager not initialized",
                },
            )
        
        if not site_manager.site_exists(site_id):
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Site not found: {site_id}",
                },
            )
        
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Use site container if available
            if agent_service and agent_service.container_manager:
                container = agent_service.container_manager.get_container(site_id, auto_create=False)
                if container:
                    alarms = container.query_alarms(
                        start_time=start_time,
                        end_time=end_time,
                        alarm_type=alarm_type,
                        severity=severity,
                        limit=limit,
                    )
                else:
                    alarms = []
            else:
                # Fallback to legacy mode
                alarms = influx_client.query_alarms(
                    start_time=start_time,
                    end_time=end_time,
                    alarm_type=alarm_type,
                    severity=severity,
                    site_id=site_id,
                    limit=limit,
                )
            
            return {
                "status": "success",
                "data": {
                    "site_id": site_id,
                    "alarms": alarms,
                    "total": len(alarms),
                },
            }
        except Exception as e:
            logger.error(f"Error getting site alarms: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/sites/{site_id}/alarms/debug")
    async def debug_site_alarms(
        site_id: str,
        time_range: str = "-24h",
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
    ):
        """Debug endpoint to check if alarms exist for a site"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "InfluxDB client not initialized"},
            )
        
        try:
            # Query alarms directly
            alarms = influx_client.query_alarms(
                site_id=site_id,
                start_time=time_range,
                limit=100,
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "site_id": site_id,
                    "time_range": time_range,
                    "alarm_count": len(alarms),
                    "alarms": alarms[:10],  # Return first 10 for debugging
                },
            )
        except Exception as e:
            logger.error(f"Error querying alarms: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
