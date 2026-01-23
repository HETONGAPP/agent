"""
Admin API routes
"""
import logging
from typing import Optional
from fastapi import Depends
from fastapi.responses import JSONResponse

from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.dependencies import (
    get_influx_client,
    get_agent_service,
    get_query_cache,
)
from ...agent.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)

def register_admin_routes(app):
    """Register admin routes"""

    @app.delete("/api/v1/admin/alarms")
    async def delete_all_alarms(
        site_id: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        query_cache = Depends(get_query_cache),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete all alarms from database (optionally from a specific site)"""
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
                if site_id:
                    # Delete from specific site container
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container:
                        deleted_count = container.delete_alarms()
                        return {
                            "status": "success",
                            "message": f"Deleted {deleted_count} alarms from site {site_id}",
                        }
                    else:
                        return JSONResponse(
                            status_code=404,
                            content={
                                "status": "error",
                                "message": f"Site container {site_id} not found",
                            },
                        )
                else:
                    # Delete from all containers
                    all_containers = agent_service.container_manager.list_containers()
                    total_deleted = 0
                    for container_site_id in all_containers:
                        try:
                            container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                            if container:
                                deleted_count = container.delete_alarms()
                                total_deleted += deleted_count
                        except Exception as e:
                            logger.warning(f"Failed to delete alarms from container {container_site_id}: {e}")
                            continue
                    # Invalidate cache
                    if query_cache:
                        query_cache.invalidate("alarms")
                        query_cache.invalidate("alarm_stats")
                    
                    return {
                        "status": "success",
                        "message": f"Deleted {total_deleted} alarms from all sites",
                    }
            else:
                # Fallback to legacy mode
                success = influx_client.delete_all_alarms()
                if success:
                    # Invalidate cache
                    if query_cache:
                        query_cache.invalidate("alarms")
                        query_cache.invalidate("alarm_stats")
                    
                    return {
                        "status": "success",
                        "message": "All alarms deleted successfully",
                    }
                else:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "status": "error",
                            "message": "Failed to delete alarms",
                        },
                    )
        except Exception as e:
            logger.error(f"Error deleting all alarms: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/admin/diagnostics")
    async def delete_all_diagnostics(
        site_id: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete all diagnostic reports from database (optionally from a specific site)"""
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
                if site_id:
                    # Delete from specific site container
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container:
                        deleted_count = container.delete_diagnostics()
                        return {
                            "status": "success",
                            "message": f"Deleted {deleted_count} diagnostics from site {site_id}",
                        }
                    else:
                        return JSONResponse(
                            status_code=404,
                            content={
                                "status": "error",
                                "message": f"Site container {site_id} not found",
                            },
                        )
                else:
                    # Delete from all containers
                    all_containers = agent_service.container_manager.list_containers()
                    total_deleted = 0
                    for container_site_id in all_containers:
                        try:
                            container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                            if container:
                                deleted_count = container.delete_diagnostics()
                                total_deleted += deleted_count
                        except Exception as e:
                            logger.warning(f"Failed to delete diagnostics from container {container_site_id}: {e}")
                            continue
                    return {
                        "status": "success",
                        "message": f"Deleted {total_deleted} diagnostics from all sites",
                    }
            else:
                # Fallback to legacy mode
                success = influx_client.delete_all_diagnostics()
                if success:
                    return {
                        "status": "success",
                        "message": "All diagnostics deleted successfully",
                    }
                else:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "status": "error",
                            "message": "Failed to delete diagnostics",
                        },
                    )
        except Exception as e:
            logger.error(f"Error deleting all diagnostics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/admin/alarms-and-diagnostics")
    async def delete_all_alarms_and_diagnostics(
        site_id: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete all alarms and diagnostic reports from database (optionally from a specific site)"""
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
                if site_id:
                    # Delete from specific site container
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container:
                        alarms_deleted = container.delete_alarms()
                        diagnostics_deleted = container.delete_diagnostics()
                        return {
                            "status": "success",
                            "message": f"Deleted {alarms_deleted} alarms and {diagnostics_deleted} diagnostics from site {site_id}",
                        }
                    else:
                        return JSONResponse(
                            status_code=404,
                            content={
                                "status": "error",
                                "message": f"Site container {site_id} not found",
                            },
                        )
                else:
                    # Delete from all containers
                    all_containers = agent_service.container_manager.list_containers()
                    total_alarms = 0
                    total_diagnostics = 0
                    for container_site_id in all_containers:
                        try:
                            container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                            if container:
                                total_alarms += container.delete_alarms()
                                total_diagnostics += container.delete_diagnostics()
                        except Exception as e:
                            logger.warning(f"Failed to delete data from container {container_site_id}: {e}")
                            continue
                    return {
                        "status": "success",
                        "message": f"Deleted {total_alarms} alarms and {total_diagnostics} diagnostics from all sites",
                    }
            else:
                # Fallback to legacy mode
                alarms_success = influx_client.delete_all_alarms()
                diagnostics_success = influx_client.delete_all_diagnostics()
            
                if alarms_success and diagnostics_success:
                    return {
                        "status": "success",
                        "message": "All alarms and diagnostics deleted successfully",
                    }
                else:
                    errors = []
                    if not alarms_success:
                        errors.append("Failed to delete alarms")
                    if not diagnostics_success:
                        errors.append("Failed to delete diagnostics")
                    
                    return JSONResponse(
                        status_code=500,
                        content={
                            "status": "partial_success",
                            "message": "; ".join(errors),
                        },
                    )
        except Exception as e:
            logger.error(f"Error deleting all alarms and diagnostics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
