"""
Site basic CRUD operations
"""
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from ...site_manager import SiteManager
from ...dependencies import (
    get_site_manager,
    get_app_state,
    get_agent_service as get_agent_service_func,
    get_influx_client,
)
from ...rate_limiter import rate_limit_dependency
from ....storage.site_container import delete_site_bucket

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    """Register basic site CRUD routes"""

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
                        # Set container manager in site_manager (and rule manager) if not already set
                        if not site_manager._container_manager:
                            site_manager.set_container_manager(agent_service.container_manager)

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
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete a site"""
        from ....core import DeviceRegistry
        from ...dependencies import get_device_registry
        from ...websocket_manager import EventType
        
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
            device_registry = get_device_registry()
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
            
            # Delete site container (bucket) - always delete bucket when site is deleted.
            # 1) Try container_manager first (clears cache, deletes if it had the container).
            # 2) Always try delete_site_bucket when influx_client is available, so the bucket
            #    is really gone even when container_manager said "not found" or wasn't available.
            agent_service = get_agent_service_func()
            if agent_service and agent_service.container_manager:
                try:
                    if agent_service.container_manager.delete_container(site_id):
                        logger.info(f"✓ Deleted container and ALL data for site {site_id} (bucket: site_{site_id})")
                    else:
                        logger.warning(f"Container for site {site_id} not found or already deleted")
                except Exception as e:
                    logger.error(f"Failed to delete container for site {site_id}: {e}", exc_info=True)
            influx_client = get_influx_client()
            if influx_client:
                try:
                    if delete_site_bucket(influx_client, site_id):
                        logger.info(f"✓ Deleted bucket site_{site_id} for site {site_id}")
                except Exception as e:
                    logger.error(f"Failed to delete bucket for site {site_id}: {e}", exc_info=True)

            # Delete site metadata from main bucket
            if site_manager._influx_storage:
                try:
                    if site_manager._influx_storage.delete_site(site_id):
                        logger.info(f"✓ Deleted site metadata from main bucket for site {site_id}")
                except Exception as e:
                    logger.error(f"Failed to delete site metadata from main bucket: {e}", exc_info=True)
            
            # Delete all device metadata for devices in this site from main bucket
            if device_ids_to_delete and site_manager._influx_storage:
                try:
                    devices_deleted = 0
                    for device_id in device_ids_to_delete:
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
