"""
Site device management routes
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from ....core import DeviceRegistry, DeviceStatus
from ....models.device_data import DeviceType
from ...site_manager import SiteManager
from ...dependencies import (
    get_site_manager,
    get_device_registry,
    get_app_state,
)
from ...websocket_manager import EventType
from ...rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    """Register site device management routes"""

    @app.post("/api/v1/sites/{site_id}/devices")
    async def add_device_to_site(
        site_id: str,
        device_data: Dict[str, Any],
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Add a device to a site"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        if not site_manager or not site_manager.site_exists(site_id):
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Site not found: {site_id}",
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
            
            # Check if device already exists in this site
            existing_device = device_registry.get_device(device_id)
            if existing_device and existing_device.status != DeviceStatus.UNREGISTERED:
                existing_site_id = existing_device.metadata.get("site_id") if existing_device.metadata else None
                if existing_site_id == site_id:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "status": "error",
                            "message": f"Device {device_id} already exists in site {site_id}",
                        },
                    )
                logger.info(f"Device {device_id} exists in site {existing_site_id}, adding to site {site_id}")
            
            # Prepare metadata with site_id
            metadata = device_data.get("metadata", {})
            metadata["site_id"] = site_id
            if device_data.get("brand"):
                metadata["brand"] = device_data["brand"]
            if device_data.get("model"):
                metadata["model"] = device_data["model"]
            metadata["source"] = "manual"
            metadata["registered_via"] = "frontend"
            metadata["registered_at"] = datetime.utcnow().isoformat()
            
            # Register device
            device = device_registry.register_device(
                device_id=device_id,
                device_type=device_type,
                integration_name=integration_name,
                metadata=metadata,
            )
            
            # Auto-create rules for this device
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
            
            # Broadcast device added event via WebSocket
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.DEVICE_ADDED, {"data": device.to_dict()}
                )
            
            return {
                "status": "success",
                "message": f"Device {device_id} added to site {site_id}",
                "data": device.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error adding device to site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/sites/{site_id}/devices")
    async def get_site_devices(
        site_id: str,
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get devices for a specific site"""
        if not device_registry:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Device registry not initialized",
                },
            )
        
        if not site_manager or not site_manager.site_exists(site_id):
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"Site not found: {site_id}",
                },
            )
        
        try:
            # Get all devices and filter by site_id in metadata
            all_devices = device_registry.get_all_devices()
            logger.debug(f"[get_site_devices] Total devices in registry: {len(all_devices)}")
            site_devices = []
            
            # Get site configuration to check enabled device types
            site_config = site_manager.get_site(site_id)
            enabled_device_types = set()
            if site_config:
                devices_config = site_config.get("devices_config") or site_config.get("devices", {})
                for device_type, config in devices_config.items():
                    if isinstance(config, dict) and config.get("enabled", False):
                        enabled_device_types.add(device_type.upper())
            
            # Get all sites to check if this is the only site
            all_sites = site_manager.get_all_sites()
            is_only_site = len(all_sites) == 1
            
            # Calculate inactive timeout
            inactive_timeout_seconds = 30
            now = datetime.now(timezone.utc)
            
            for device in all_devices:
                device_dict = device.to_dict()
                device_metadata = device_dict.get("metadata", {})
                device_site_id = device_metadata.get("site_id")
                device_type = device_dict.get("device_type", "").upper()
                
                # Check if device belongs to this site
                if device_site_id == site_id:
                    # Check if device should be considered inactive
                    device_status = device_dict.get("status", "registered")
                    last_seen_str = device_dict.get("last_seen")
                    
                    if device_status == "active" and last_seen_str:
                        try:
                            if isinstance(last_seen_str, str):
                                if last_seen_str.endswith("Z"):
                                    last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                                else:
                                    last_seen = datetime.fromisoformat(last_seen_str)
                                if last_seen.tzinfo is None:
                                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                            else:
                                last_seen = last_seen_str
                            
                            if last_seen.tzinfo is None:
                                last_seen = last_seen.replace(tzinfo=timezone.utc)
                            
                            time_since_last_seen = (now - last_seen).total_seconds()
                            
                            if time_since_last_seen > inactive_timeout_seconds:
                                device_dict["status"] = "inactive"
                        except Exception as e:
                            logger.warning(f"[get_site_devices] Error parsing last_seen for device {device.device_id}: {e}")
                    
                    site_devices.append(device_dict)
                elif device_site_id is None:
                    # Auto-assign if only site or device type enabled
                    if is_only_site or device_type in enabled_device_types:
                        device.metadata["site_id"] = site_id
                        updated_device = device_registry.register_device(
                            device_id=device.device_id,
                            device_type=device.device_type,
                            integration_name=device.integration_name,
                            metadata=device.metadata,
                        )
                        site_devices.append(updated_device.to_dict())
            
            logger.info(f"[get_site_devices] Returning {len(site_devices)} devices for site {site_id}")
            return {
                "status": "success",
                "data": {
                    "site_id": site_id,
                    "devices": site_devices,
                    "total": len(site_devices),
                },
            }
        except Exception as e:
            logger.error(f"Error getting site devices: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
