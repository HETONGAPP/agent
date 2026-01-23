"""
Device management API routes
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request, Depends, Query
from fastapi.responses import JSONResponse

from ...core import DeviceRegistry
from ...core.device_registry import DeviceStatus
from ...models.device_data import DeviceType
from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.dependencies import (
    get_device_registry,
    get_influx_client,
    get_agent_service,
    get_app_state,
)
from ...agent.rate_limiter import rate_limit_dependency
from ...agent.websocket_manager import EventType

logger = logging.getLogger(__name__)


def register_device_routes(app):
    """Register device management routes"""
    
    @app.get("/api/v1/devices/{device_id}/data")
    async def get_device_data(
        device_id: str,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """
        Get device data from InfluxDB (historical data)
        
        NOTE: Real-time device data is received via MQTT, not through this endpoint.
        This endpoint only returns historical data stored in InfluxDB.
        """
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        device = device_registry.get_device(device_id)
        if not device:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Device not found: {device_id}",
                },
            )
        
        return JSONResponse(
            status_code=501,
            content={
                "status": "error",
                "message": (
                    f"Device data for {device_id} should be received via MQTT. "
                    f"Real-time data is not available through this endpoint. "
                    f"Use InfluxDB query API to retrieve historical data."
                ),
            },
        )

    @app.post("/api/v1/devices")
    async def register_device(
        device_data: Dict[str, Any],
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Register a new device (frontend-initiated registration)"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            device_id = device_data.get("device_id")
            if not device_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "device_id is required",
                    },
                )
            
            device_type_str = device_data.get("device_type")
            if not device_type_str:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "device_type is required",
                    },
                )
            
            try:
                device_type = DeviceType(device_type_str.upper())
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": f"Invalid device_type: {device_type_str}",
                    },
                )
            
            integration_name = device_data.get("integration_name", "")
            metadata = device_data.get("metadata", {})
            
            # Check if device already exists in the same site (device_id can be reused across different sites)
            site_id = metadata.get("site_id")
            existing_device = device_registry.get_device(device_id)
            if existing_device and existing_device.status != DeviceStatus.UNREGISTERED:
                # Check if device belongs to a different site
                existing_site_id = existing_device.metadata.get("site_id") if existing_device.metadata else None
                if site_id and existing_site_id == site_id:
                    # Device already exists in the same site
                    return JSONResponse(
                        status_code=409,
                        content={
                            "status": "error",
                            "message": f"Device {device_id} already exists in site {site_id}",
                        },
                    )
                elif site_id and existing_site_id and existing_site_id != site_id:
                    # Device exists but in a different site - allow re-registration by updating metadata
                    # This allows the same device_id to be used in different sites
                    logger.info(f"Device {device_id} exists in site {existing_site_id}, updating metadata for site {site_id}")
                    # Update the existing device's metadata to reflect the new site
                    if existing_device.metadata:
                        existing_device.metadata.update(metadata)
                    else:
                        existing_device.metadata = metadata
                    existing_device.update_last_seen()
                    return {
                        "status": "success",
                        "message": f"Device {device_id} updated for site {site_id}",
                        "data": existing_device.to_dict(),
                    }
                # If no site_id provided or existing device has no site_id, continue with normal registration
            
            if not metadata:
                metadata = {}
            metadata["source"] = "manual"
            metadata["registered_via"] = "frontend"
            metadata["registered_at"] = datetime.utcnow().isoformat()
            
            device = device_registry.register_device(
                device_id=device_id,
                device_type=device_type,
                integration_name=integration_name,
                metadata=metadata,
            )
            
            # Auto-create rules for this device if site_id is provided
            site_id = metadata.get("site_id")
            if site_id:
                from ...agent.dependencies import get_site_manager
                site_manager = get_site_manager()
                if site_manager:
                    try:
                        rules_created = site_manager.create_device_rules(
                            device_id=device_id,
                            device_type=device_type.value,
                            site_id=site_id
                        )
                        logger.info(f"Auto-created {rules_created} rules for device {device_id} in site {site_id}")
                    except Exception as e:
                        logger.warning(f"Failed to auto-create rules for device {device_id}: {e}")
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.DEVICE_ADDED, {"data": device.to_dict()}
                )
            
            logger.info(f"Device registered via API: {device_id} (type={device_type.value}, site={metadata.get('site_id', 'N/A')})")
            
            return {
                "status": "success",
                "message": f"Device {device_id} registered successfully",
                "data": device.to_dict(),
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error registering device: {e}", exc_info=True)
            logger.error(f"Device data: {device_data}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error", 
                    "message": f"Failed to register device: {error_msg}",
                },
            )
    
    @app.get("/api/v1/devices")
    async def list_devices(
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        integration_name: Optional[str] = None,
        site_id: Optional[str] = None,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """List all registered devices with optional filters"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            devices = device_registry.get_all_devices()
            inactive_timeout_seconds = 30
            now = datetime.now(timezone.utc)
            
            for device in devices:
                if device.status == DeviceStatus.ACTIVE and device.last_seen:
                    try:
                        if isinstance(device.last_seen, str):
                            if device.last_seen.endswith("Z"):
                                last_seen_dt = datetime.fromisoformat(device.last_seen.replace("Z", "+00:00"))
                            else:
                                last_seen_dt = datetime.fromisoformat(device.last_seen)
                            if last_seen_dt.tzinfo is None:
                                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                        else:
                            last_seen_dt = device.last_seen
                            if last_seen_dt.tzinfo is None:
                                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                        
                        time_since_last_seen = (now - last_seen_dt).total_seconds()
                        if time_since_last_seen > inactive_timeout_seconds and device.status == DeviceStatus.ACTIVE:
                            device.mark_inactive()
                            if device_registry._influx_storage:
                                try:
                                    device_dict = device.to_dict()
                                    device_registry._influx_storage.save_device(device_dict)
                                except Exception as e:
                                    logger.debug(f"Failed to save inactive status for device {device.device_id}: {e}")
                            logger.debug(
                                f"[list_devices] Device {device.device_id} marked as inactive "
                                f"(last_seen: {last_seen_dt.isoformat()}, {time_since_last_seen:.0f}s ago)"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[list_devices] Error parsing last_seen for device {device.device_id}: {e}",
                            exc_info=True
                        )
            
            if device_type:
                try:
                    device_type_enum = DeviceType(device_type.upper())
                    devices = [d for d in devices if d.device_type == device_type_enum]
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": f"Invalid device_type: {device_type}",
                        },
                    )
            
            if status:
                try:
                    status_enum = DeviceStatus(status.lower())
                    devices = [d for d in devices if d.status == status_enum]
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": f"Invalid status: {status}",
                        },
                    )
            
            if site_id:
                devices = [
                    d for d in devices
                    if d.to_dict().get("metadata", {}).get("site_id") == site_id
                ]
            
            if integration_name:
                devices = [d for d in devices if d.integration_name == integration_name]
            
            return {
                "status": "success",
                "data": {
                    "devices": [device.to_dict() for device in devices],
                    "total": len(devices),
                },
            }
        except Exception as e:
            logger.error(f"Error listing devices: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/devices/stats")
    async def get_device_stats(
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get device statistics"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            devices = device_registry.get_all_devices()
            
            status_counts = {}
            for status in DeviceStatus:
                status_counts[status.value] = sum(1 for d in devices if d.status == status)
            
            type_counts = {}
            for device_type in DeviceType:
                type_counts[device_type.value] = sum(1 for d in devices if d.device_type == device_type)
            
            integration_counts = {}
            for device in devices:
                integration_counts[device.integration_name] = integration_counts.get(device.integration_name, 0) + 1
            
            return {
                "status": "success",
                "data": {
                    "total": len(devices),
                    "by_status": status_counts,
                    "by_type": type_counts,
                    "by_integration": integration_counts,
                },
            }
        except Exception as e:
            logger.error(f"Error getting device stats: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/devices/{device_id}")
    async def get_device(
        device_id: str,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get device details by ID"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            device = device_registry.get_device(device_id)
            if not device:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Device not found: {device_id}",
                    },
                )
            
            return {
                "status": "success",
                "data": device.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error getting device: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.put("/api/v1/devices/{device_id}/status")
    async def update_device_status(
        device_id: str,
        request: Request,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Update device status"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            payload = await request.json()
            status_str = payload.get("status")
            
            if not status_str:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Missing required field: status",
                    },
                )
            
            try:
                status = DeviceStatus(status_str.lower())
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": f"Invalid status: {status_str}. Valid values: {[s.value for s in DeviceStatus]}",
                    },
                )
            
            device = device_registry.get_device(device_id)
            if not device:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Device not found: {device_id}",
                    },
                )
            
            device_registry.update_device_status(device_id, status)
            updated_device = device_registry.get_device(device_id)
            
            websocket_manager = get_app_state().get("websocket_manager")
            if websocket_manager and updated_device:
                await websocket_manager.broadcast(
                    EventType.DEVICE_STATUS_CHANGED,
                    {
                        "device_id": device_id,
                        "status": status.value,
                        "device": updated_device.to_dict(),
                    },
                )
            
            return {
                "status": "success",
                "data": updated_device.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error updating device status: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.put("/api/v1/devices/{device_id}")
    async def update_device(
        device_id: str,
        device_data: Dict[str, Any],
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Update device information (integration_name, metadata)"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            integration_name = device_data.get("integration_name")
            metadata = device_data.get("metadata")
            
            updated_device = device_registry.update_device(
                device_id=device_id,
                integration_name=integration_name,
                metadata=metadata,
            )
            
            if not updated_device:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Device not found: {device_id}",
                    },
                )
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.DEVICE_UPDATED,
                    {
                        "device_id": device_id,
                        "device": updated_device.to_dict(),
                        "reason": "device_updated",
                    },
                )
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "reason": "device_updated",
                        "device_id": device_id,
                    },
                )
            
            return {
                "status": "success",
                "data": updated_device.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error updating device: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/devices/{device_id}")
    async def delete_device(
        device_id: str,
        delete_data: bool = Query(False, description="Whether to delete historical data"),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """
        Unregister a device
        
        Args:
            device_id: Device ID to delete
            delete_data: If True, also delete all historical data (device_data, alarms, diagnostics)
        """
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        try:
            device = device_registry.get_device(device_id)
            if not device:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Device not found: {device_id}",
                    },
                )
            
            site_id = device.metadata.get("site_id") if device.metadata else None
            
            if delete_data:
                try:
                    logger.info(f"Deleting historical data for device {device_id} (site: {site_id})")
                    
                    if agent_service and agent_service.container_manager and site_id:
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            container.delete_device_data(device_ids=[device_id])
                            container.delete_alarms(device_ids=[device_id])
                            container.delete_diagnostics(device_ids=[device_id])
                        else:
                            logger.warning(f"Site container {site_id} not found, cannot delete device data")
                    elif influx_client:
                        influx_client.delete_device_data(device_id)
                    
                    logger.info(f"Deleted data for device {device_id}")
                except Exception as e:
                    logger.error(f"Failed to delete historical data for device {device_id}: {e}", exc_info=True)
            
            success = device_registry.unregister_device(device_id)
            if not success:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Failed to unregister device {device_id}",
                    },
                )
            
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.DEVICE_REMOVED, {"data": device.to_dict()}
                )
            
            logger.info(f"Device unregistered via API: {device_id} (delete_data={delete_data})")
            
            return {
                "status": "success",
                "message": f"Device {device_id} unregistered successfully" + 
                          (" (historical data deleted)" if delete_data else " (historical data preserved)"),
            }
        except Exception as e:
            logger.error(f"Error deleting device: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )

