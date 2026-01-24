"""
Site management API routes
"""
import logging
from datetime import datetime, timezone, UTC
from typing import Optional, Dict, Any
from fastapi import Depends, Query
from fastapi.responses import JSONResponse

from ...core import DeviceRegistry
from ...models.device_data import DeviceType
from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.site_manager import SiteManager
from ...agent.websocket_manager import WebSocketManager, EventType
from ...agent.dependencies import (
    get_site_manager,
    get_device_registry,
    get_influx_client,
    get_agent_service,
    get_app_state,
    get_agent_service as get_agent_service_func,
    get_postgres_metadata_storage,
)
from ...agent.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_site_routes(app):
    """Register site management routes"""

    @app.post("/api/v1/sites")
    async def create_site(
        site_data: Dict[str, Any],
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Create a new site"""
        if not site_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Site manager not initialized",
                },
            )
        
        try:
            site_id = site_data.get("site_id")
            if not site_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "site_id is required",
                    },
                )
            
            # Clear cache before checking to ensure fresh data
            site_manager._site_configs_cache.pop(site_id, None)
            logger.info(f"Checking if site {site_id} exists (cache cleared)")
            
            # Check if site already exists
            site_exists = site_manager.site_exists(site_id)
            logger.info(f"site_exists('{site_id}') returned: {site_exists}")
            
            if site_exists:
                # Double-check by querying InfluxDB directly
                if site_manager._influx_storage:
                    try:
                        direct_check = site_manager._influx_storage.get_site(site_id)
                        logger.info(f"Direct InfluxDB query for site {site_id}: {direct_check is not None}")
                        if direct_check:
                            logger.warning(f"Site {site_id} exists in InfluxDB: {direct_check}")
                        else:
                            logger.warning(f"Site {site_id} does not exist in InfluxDB, but site_exists returned True - possible cache issue")
                    except Exception as e:
                        logger.error(f"Error checking site directly in InfluxDB: {e}")
                
                return JSONResponse(
                    status_code=409,
                    content={
                        "status": "error",
                        "message": f"Site {site_id} already exists",
                    },
                )
            
            # Check for orphaned bucket (bucket exists but site config doesn't)
            # Clean it up before creating new site
            agent_service = get_agent_service_func()
            if agent_service and agent_service.container_manager:
                try:
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container and container.exists():
                        # Orphaned bucket found - delete it
                        logger.info(f"Found orphaned bucket for site {site_id}, cleaning up...")
                        agent_service.container_manager.delete_container(site_id)
                        logger.info(f"✓ Cleaned up orphaned bucket for site {site_id}")
                except Exception as e:
                    logger.warning(f"Error checking/cleaning orphaned bucket for site {site_id}: {e}")
            
            # Create site
            success = site_manager.create_site(site_data)
            if success:
                # Create site container (bucket) if container manager is available
                if agent_service and agent_service.container_manager:
                    try:
                        # Set container manager in site_manager if not already set
                        if not site_manager._container_manager:
                            site_manager._container_manager = agent_service.container_manager
                        
                        container = agent_service.container_manager.get_container(site_id, auto_create=True)
                        logger.info(f"✓ Created container for site {site_id}")
                        
                        # Load universal rules to site container database
                        try:
                            rules_loaded = site_manager.load_universal_rules_to_site(site_id)
                            if rules_loaded > 0:
                                logger.info(f"✓ Loaded {rules_loaded} universal rules to site {site_id}")
                            else:
                                logger.info(f"ℹ No new universal rules loaded for site {site_id} (may already exist)")
                        except Exception as e:
                            logger.warning(f"Failed to load universal rules to site {site_id}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to create container for site {site_id}: {e}")
                
                # Reload to get the new site
                site = site_manager.get_site(site_id)
                return {
                    "status": "success",
                    "message": f"Site {site_id} created successfully",
                    "data": site,
                }
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Failed to create site {site_id}",
                    },
                )
        except Exception as e:
            logger.error(f"Error creating site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/sites")
    async def list_sites(
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """List all sites"""
        if not site_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Site manager not initialized",
                },
            )
        
        try:
            sites = site_manager.get_all_sites()
            return {
                "status": "success",
                "data": {
                    "sites": sites,
                    "total": len(sites),
                },
            }
        except Exception as e:
            logger.error(f"Error listing sites: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/sites/{site_id}")
    async def get_site(
        site_id: str,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get site details"""
        if not site_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "Site manager not initialized",
                },
            )
        
        try:
            site = site_manager.get_site(site_id)
            if not site:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Site not found: {site_id}",
                    },
                )
            
            # Get site rules
            rules = site_manager.get_site_rules(site_id)
            site["rules"] = rules
            site["rules_count"] = len(rules)
            
            return {
                "status": "success",
                "data": site,
            }
        except Exception as e:
            logger.error(f"Error getting site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.put("/api/v1/sites/{site_id}")
    async def update_site(
        site_id: str,
        site_data: Dict[str, Any],
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Update site configuration"""
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
            
            success = site_manager.update_site(site_id, site_data)
            if not success:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Failed to update site {site_id}",
                    },
                )
            
            # Reload to get updated site
            site = site_manager.get_site(site_id)
            
            # Also reload in rule engine if available
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            logger.info(f"Site {site_id} updated via API")
            
            return {
                "status": "success",
                "message": f"Site {site_id} updated successfully",
                "data": site,
            }
        except Exception as e:
            logger.error(f"Error updating site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/sites/{site_id}")
    async def delete_site(
        site_id: str,
        delete_data: bool = Query(False, description="If true, delete all site data (alarms, diagnostics, device data)"),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete a site"""
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
            
            # Collect all devices for this site BEFORE deleting them
            # We need device IDs to delete metadata from main bucket
            devices_to_delete = []
            device_ids_to_delete = []
            if device_registry:
                try:
                    all_devices = device_registry.get_all_devices()
                    for device in all_devices:
                        device_metadata = device.metadata or {}
                        device_site_id = device_metadata.get("site_id")
                        if device_site_id == site_id:
                            devices_to_delete.append(device)
                            device_ids_to_delete.append(device.device_id)
                except Exception as e:
                    logger.error(f"Error collecting devices for site {site_id}: {e}", exc_info=True)
                    
            # Delete all devices associated with this site from device registry
            if device_registry and devices_to_delete:
                try:
                    deleted_device_count = 0
                    app_state = get_app_state()
                    websocket_manager = app_state.get("websocket_manager")
                    
                    for device in devices_to_delete:
                        if device_registry.unregister_device(device.device_id):
                            deleted_device_count += 1
                            logger.info(f"Unregistered device {device.device_id} for deleted site {site_id}")
                            
                            if websocket_manager:
                                try:
                                    await websocket_manager.broadcast(
                                        EventType.DEVICE_REMOVED, {"data": device.to_dict()}
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to broadcast device removal for {device.device_id}: {e}")
                    
                    if deleted_device_count > 0:
                        logger.info(f"✓ Unregistered {deleted_device_count} device(s) for site {site_id}")
                except Exception as e:
                    logger.error(f"Error deleting devices for site {site_id}: {e}", exc_info=True)
            
            # Delete site container (bucket) - always delete bucket when site is deleted
            # Site and bucket have 1:1 relationship, so bucket should always be deleted with site
            # This deletes ALL data: device_data, alarms, rules, diagnostics, etc.
            agent_service = get_agent_service_func()
            if agent_service and agent_service.container_manager:
                try:
                    # Always delete the entire container (bucket) - this deletes all site data
                    # Including: device_data, alarms, rules, diagnostics, and all other measurements
                    container_deleted = agent_service.container_manager.delete_container(site_id)
                    if container_deleted:
                        logger.info(f"✓ Deleted container and ALL data for site {site_id} (bucket: site_{site_id})")
                    else:
                        logger.warning(f"Container for site {site_id} not found or already deleted")
                except Exception as e:
                    logger.error(f"Failed to delete container for site {site_id}: {e}", exc_info=True)
            
            # Delete site metadata from main bucket (sites measurement)
            # This is separate from the site bucket and contains site configuration
            if site_manager._influx_storage:
                try:
                    if site_manager._influx_storage.delete_site(site_id):
                        logger.info(f"✓ Deleted site metadata from main bucket for site {site_id}")
                except Exception as e:
                    logger.error(f"Failed to delete site metadata from main bucket: {e}", exc_info=True)
            
            # Delete all device metadata for devices in this site from main bucket
            # Use the device IDs we collected earlier (before unregistering)
            if device_ids_to_delete and site_manager._influx_storage:
                try:
                    devices_deleted = 0
                    for device_id in device_ids_to_delete:
                        # Pass site_id to delete_device to ensure correct bucket is targeted
                        if site_manager._influx_storage.delete_device(device_id, site_id=site_id):
                            devices_deleted += 1
                            logger.debug(f"Deleted device metadata for {device_id}")
                    if devices_deleted > 0:
                        logger.info(f"✓ Deleted {devices_deleted} device metadata records from main bucket")
                except Exception as e:
                    logger.error(f"Failed to delete device metadata from main bucket: {e}", exc_info=True)
            
            # Delete all diagnostic reports for this site from PostgreSQL
            if site_manager._postgres_storage:
                try:
                    diagnostics_deleted = site_manager._postgres_storage.delete_diagnostics_by_site(site_id)
                    if diagnostics_deleted > 0:
                        logger.info(f"✓ Deleted {diagnostics_deleted} diagnostic report(s) from PostgreSQL for site {site_id}")
                except Exception as e:
                    logger.error(f"Failed to delete diagnostic reports from PostgreSQL for site {site_id}: {e}", exc_info=True)
            
            success = site_manager.delete_site(site_id)
            if not success:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Failed to delete site {site_id}",
                    },
                )
            
            # Also reload in rule engine if available
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            logger.info(f"✓ Site {site_id} completely deleted via API (all data removed)")
            
            return {
                "status": "success",
                "message": f"Site {site_id} and all associated data deleted successfully",
            }
        except Exception as e:
            logger.error(f"Error deleting site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
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
                    # Device already exists in the same site
                    return JSONResponse(
                        status_code=409,
                        content={
                            "status": "error",
                            "message": f"Device {device_id} already exists in site {site_id}",
                        },
                    )
                # Device exists but in a different site - this is allowed
                logger.info(f"Device {device_id} exists in site {existing_site_id}, adding to site {site_id}")
            
            # Prepare metadata with site_id and other device info
            metadata = device_data.get("metadata", {})
            metadata["site_id"] = site_id
            if device_data.get("brand"):
                metadata["brand"] = device_data["brand"]
            if device_data.get("model"):
                metadata["model"] = device_data["model"]
            metadata["source"] = "manual"
            metadata["registered_via"] = "frontend"
            metadata["registered_at"] = datetime.utcnow().isoformat()
            
            # Register device (will update if exists, create if new)
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
                logger.debug(f"[get_site_devices] Enabled device types for site {site_id}: {enabled_device_types}")
            
            # Get all sites to check if this is the only site
            all_sites = site_manager.get_all_sites()
            is_only_site = len(all_sites) == 1
            logger.debug(f"[get_site_devices] Is only site: {is_only_site}, total sites: {len(all_sites)}")
            
            # Calculate inactive timeout (30 seconds for fast response when device disconnects)
            inactive_timeout_seconds = 30
            now = datetime.now(timezone.utc)
            
            for device in all_devices:
                device_dict = device.to_dict()
                device_metadata = device_dict.get("metadata", {})
                device_site_id = device_metadata.get("site_id")
                device_type = device_dict.get("device_type", "").upper()
                
                # Check if device belongs to this site
                if device_site_id == site_id:
                    logger.debug(f"[get_site_devices] Device {device.device_id} belongs to site {site_id}")
                    
                    # Check if device should be considered inactive based on last_seen
                    device_status = device_dict.get("status", "registered")
                    last_seen_str = device_dict.get("last_seen")
                    
                    if device_status == "active" and last_seen_str:
                        try:
                            # Parse last_seen timestamp
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
                            logger.debug(
                                f"[get_site_devices] Device {device.device_id} status check: "
                                f"status={device_status}, last_seen={last_seen}, "
                                f"time_since={time_since_last_seen:.0f}s, timeout={inactive_timeout_seconds}s"
                            )
                            
                            if time_since_last_seen > inactive_timeout_seconds:
                                device_dict["status"] = "inactive"
                                logger.info(
                                    f"[get_site_devices] Device {device.device_id} marked as inactive "
                                    f"(last_seen: {last_seen.isoformat()}, {time_since_last_seen:.0f}s ago, "
                                    f"threshold: {inactive_timeout_seconds}s)"
                                )
                        except Exception as e:
                            logger.warning(
                                f"[get_site_devices] Error parsing last_seen for device {device.device_id}: {e}"
                            )
                    
                    site_devices.append(device_dict)
                elif device_site_id is None:
                    # Device has no site_id assigned
                    # If this is the only site, or if device type is enabled for this site, include it
                    if is_only_site or device_type in enabled_device_types:
                        logger.info(
                            f"[get_site_devices] Auto-assigning device {device.device_id} "
                            f"(type={device_type}) to site {site_id} "
                            f"(is_only_site={is_only_site}, enabled={device_type in enabled_device_types})"
                        )
                        # Auto-assign site_id to device metadata
                        device.metadata["site_id"] = site_id
                        # Update device in registry to persist the change
                        updated_device = device_registry.register_device(
                            device_id=device.device_id,
                            device_type=device.device_type,
                            integration_name=device.integration_name,
                            metadata=device.metadata,
                        )
                        updated_device_dict = updated_device.to_dict()
                        site_devices.append(updated_device_dict)
                    else:
                        logger.debug(
                            f"[get_site_devices] Device {device.device_id} (type={device_type}) "
                            f"not assigned to site {site_id} (not only site and type not enabled)"
                        )
            
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
                    # Determine actual status based on last_seen
                    device_status = device.status.value
                    last_seen = device.last_seen
                    
                    # If device is marked as active but hasn't been seen recently, consider it inactive
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
                            logger.debug(
                                f"[get_site_stats] Device {device.device_id} status check: "
                                f"status={device_status}, last_seen={last_seen_dt.isoformat()}, "
                                f"time_since={time_since_last_seen:.0f}s, timeout={inactive_timeout_seconds}s"
                            )
                            
                            if time_since_last_seen > inactive_timeout_seconds:
                                device_status = "inactive"
                                logger.info(
                                    f"[get_site_stats] Device {device.device_id} marked as inactive "
                                    f"(last_seen: {last_seen_dt.isoformat()}, {time_since_last_seen:.0f}s ago)"
                                )
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
                    # Use site container if available
                    if agent_service and agent_service.container_manager:
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            alarms = container.query_alarms(limit=10000)
                        else:
                            alarms = []
                    else:
                        # Fallback to legacy mode
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
    
    @app.get("/api/v1/sites/{site_id}/diagnostics")
    async def get_site_diagnostics(
        site_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 100,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get diagnostic reports for a specific site"""
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
                    diagnostics = container.query_diagnostics(
                        start_time=start_time,
                        end_time=end_time,
                        risk_level=risk_level,
                        limit=limit,
                    )
                else:
                    diagnostics = []
            else:
                # Fallback to legacy mode
                diagnostics = influx_client.query_diagnostics(
                    start_time=start_time,
                    end_time=end_time,
                    risk_level=risk_level,
                    site_id=site_id,
                    limit=limit,
                )
            
            return {
                "status": "success",
                "data": {
                    "site_id": site_id,
                    "diagnostics": diagnostics,
                    "total": len(diagnostics),
                },
            }
        except Exception as e:
            logger.error(f"Error getting site diagnostics: {e}", exc_info=True)
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

    @app.post("/api/v1/sites/{site_id}/diagnostics/generate")
    async def generate_site_diagnostic(
        site_id: str,
        time_range: str = "-24h",
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Manually trigger diagnostic agent analysis for a site"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        if not agent_service or not agent_service.llm_diagnostic_service:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "LLM diagnostic service not initialized",
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
            # Get LLM client from diagnostic service
            llm_client = agent_service.llm_diagnostic_service.llm_client
            
            # Get WebSocket manager for real-time updates (optional)
            from ...agent.dependencies import get_app_state
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager") if app_state else None
            
            # Generate diagnostic ID
            import time
            diagnostic_id = f"diagnostic_{site_id}_{int(time.time())}"
            
            # Import diagnostic agent components
            from ...diagnostic_agent.planner import DiagnosticPlanner
            from ...diagnostic_agent.executor import DiagnosticExecutor
            from ...diagnostic_agent.agents import (
                DataCollectorAgent,
                AlarmAnalyzerAgent,
                DeviceAnalyzerAgent,
                TrendAnalyzerAgent,
                CorrelationAgent,
                ReportGeneratorAgent,
            )
            
            # Create planner
            planner = DiagnosticPlanner(llm_client)
            
            # Plan diagnostic tasks
            task_manager = await planner.plan_diagnostic(
                site_id=site_id,
                time_range=time_range,
            )
            
            # Create agents
            agents = {
                "DataCollectorAgent": DataCollectorAgent(
                    llm_client=llm_client,
                    influx_client=influx_client,
                    device_registry=device_registry,
                ),
                "AlarmAnalyzerAgent": AlarmAnalyzerAgent(llm_client=llm_client),
                "DeviceAnalyzerAgent": DeviceAnalyzerAgent(llm_client=llm_client),
                "TrendAnalyzerAgent": TrendAnalyzerAgent(llm_client=llm_client),
                "CorrelationAgent": CorrelationAgent(llm_client=llm_client),
                "ReportGeneratorAgent": ReportGeneratorAgent(llm_client=llm_client),
            }
            
            # Create executor with WebSocket support
            executor = DiagnosticExecutor(
                task_manager=task_manager,
                agents=agents,
                context={
                    "site_id": site_id,
                    "time_range": time_range,
                },
                websocket_manager=websocket_manager,
                diagnostic_id=diagnostic_id,
            )
            
            # Execute all tasks
            results = await executor.execute_ready_tasks()
            
            # Get final report (from ReportGeneratorAgent)
            final_task = None
            for task in task_manager.tasks:
                if task.status.value == "completed" and task.agent == "ReportGeneratorAgent":
                    final_task = task
                    break
            
            # If no report generator, use last completed task
            if not final_task:
                for task in reversed(task_manager.tasks):
                    if task.status.value == "completed":
                        final_task = task
                        break
            
            # Extract diagnostic report from result
            diagnostic_report = None
            if final_task and final_task.result:
                result = final_task.result
                if result.get("status") == "success" and result.get("report"):
                    # Extract DiagnosticReport from result
                    from ...models.diagnostic import DiagnosticReport
                    report_dict = result.get("report")
                    if isinstance(report_dict, dict):
                        diagnostic_report = DiagnosticReport.from_dict(report_dict)
                    else:
                        diagnostic_report = report_dict
            
            # If no report found, create a fallback
            if not diagnostic_report:
                from ...models.diagnostic import DiagnosticReport, RiskLevel
                diagnostic_report = DiagnosticReport(
                    alarm_id=f"site_{site_id}_diagnostic_{int(time.time())}",
                    current_status=f"Diagnostic analysis completed for site {site_id}",
                    risk_level=RiskLevel.MEDIUM,
                    possible_causes=["Analysis completed", "Multiple data sources analyzed"],
                    recommended_actions=["Review analysis results", "Take appropriate actions"],
                    references=[],
                    generated_at=datetime.now(UTC),
                    markdown="# Diagnostic Report\n\nAnalysis completed.",
                )
            
            # Store diagnostic to InfluxDB
            if influx_client:
                try:
                    # Convert DiagnosticReport to dict
                    if hasattr(diagnostic_report, 'to_dict'):
                        diagnostic_dict = diagnostic_report.to_dict()
                    else:
                        diagnostic_dict = diagnostic_report
                    
                    # Get alarm_id from diagnostic
                    alarm_id = diagnostic_dict.get('alarm_id') or diagnostic_report.alarm_id if hasattr(diagnostic_report, 'alarm_id') else f"site_{site_id}_diagnostic_{int(time.time())}"
                    
                    # Ensure timestamp is set
                    if "timestamp" not in diagnostic_dict:
                        diagnostic_dict["timestamp"] = datetime.now(UTC)
                    
                    # Ensure metadata exists
                    if "metadata" not in diagnostic_dict:
                        diagnostic_dict["metadata"] = {}
                    diagnostic_dict["metadata"]["site_id"] = site_id
                    # Set alarm_type for site diagnostics (so they appear in diagnostics list)
                    if "alarm_type" not in diagnostic_dict.get("metadata", {}):
                        diagnostic_dict["metadata"]["alarm_type"] = "site_diagnostic"
                    
                    if agent_service and agent_service.container_manager:
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            container.write_diagnostic(alarm_id, diagnostic_dict, flush=True)
                        else:
                            influx_client.write_diagnostic(alarm_id, diagnostic_dict, site_id=site_id, flush=True)
                    else:
                        influx_client.write_diagnostic(alarm_id, diagnostic_dict, site_id=site_id, flush=True)
                    
                    # Also save to PostgreSQL for metadata storage
                    if postgres_storage:
                        try:
                            # Prepare diagnostic data for PostgreSQL
                            diagnostic_metadata = {
                                "alarm_id": alarm_id,
                                "site_id": site_id,
                                "risk_level": diagnostic_dict.get("risk_level", "Unknown"),
                                "diagnostic_name": diagnostic_dict.get("diagnostic_name", ""),
                                "metadata": diagnostic_dict.get("metadata", {}),
                            }
                            # Extract device_id and device_type from metadata if available
                            if "metadata" in diagnostic_dict:
                                metadata = diagnostic_dict["metadata"]
                                if metadata.get("device_id"):
                                    diagnostic_metadata["device_id"] = metadata["device_id"]
                                if metadata.get("device_type"):
                                    diagnostic_metadata["device_type"] = metadata["device_type"]
                                if metadata.get("alarm_type"):
                                    diagnostic_metadata["alarm_type"] = metadata["alarm_type"]
                            
                            # Set timestamp
                            if "timestamp" in diagnostic_dict:
                                diagnostic_metadata["generated_at"] = diagnostic_dict["timestamp"]
                            
                            success = postgres_storage.save_diagnostic(diagnostic_metadata)
                            if success:
                                logger.info(f"Saved diagnostic {alarm_id} to PostgreSQL")
                            else:
                                logger.warning(f"Failed to save diagnostic {alarm_id} to PostgreSQL")
                        except Exception as e:
                            logger.warning(f"Failed to save diagnostic to PostgreSQL: {e}")
                except Exception as e:
                    logger.warning(f"Failed to store diagnostic: {e}")
            
            # Broadcast diagnostic_created event via WebSocket
            if websocket_manager:
                try:
                    diagnostic_dict = diagnostic_report.to_dict() if hasattr(diagnostic_report, 'to_dict') else diagnostic_report
                    await websocket_manager.broadcast(
                        EventType.DIAGNOSTIC_CREATED,
                        {
                            "alarm_id": alarm_id,
                            "site_id": site_id,
                            "id": alarm_id,
                            "diagnostic": diagnostic_dict,
                        }
                    )
                    logger.info(f"Broadcasted diagnostic_created event for {alarm_id}")
                except Exception as e:
                    logger.warning(f"Failed to broadcast diagnostic_created event: {e}")
            
            return {
                "status": "success",
                "message": f"Diagnostic report generated for site {site_id}",
                "data": diagnostic_report.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error generating site diagnostic: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
