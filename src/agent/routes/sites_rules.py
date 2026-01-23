"""
Site rules management API routes
"""
import logging
from typing import Optional, Dict, Any
from fastapi import Depends
from fastapi.responses import JSONResponse

from ...core import DeviceRegistry
from ...agent.site_manager import SiteManager
from ...agent.websocket_manager import WebSocketManager, EventType
from ...agent.dependencies import (
    get_site_manager,
    get_device_registry,
    get_app_state,
    get_query_cache,
)
from ...agent.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_site_rules_routes(app):
    """Register site rules management routes"""

    @app.get("/api/v1/sites/{site_id}/rules")
    async def get_site_rules(
        site_id: str,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get rules for a specific site, grouped by device"""
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
            
            # Get site-specific rules
            site_rules = site_manager.get_site_rules(site_id)
            
            # Get all rules for this site (including global rules merged with site rules)
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            all_rules = []
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                # Use site rule manager to get merged rules (global + site-specific)
                all_rules = rule_engine.site_rule_manager.get_rules_for_site(site_id)
            else:
                # Fallback to site-specific rules only
                all_rules = site_rules
            
            # Get all devices for this site
            site_devices = []
            if device_registry:
                all_devices = device_registry.get_all_devices()
                for device in all_devices:
                    device_dict = device.to_dict()
                    device_metadata = device_dict.get("metadata", {})
                    device_site_id = device_metadata.get("site_id")
                    if device_site_id == site_id:
                        site_devices.append(device_dict)
            
            # Group rules by device
            device_rules_map: Dict[str, Dict[str, Any]] = {}
            
            for device in site_devices:
                device_id = device.get("device_id")
                device_type = device.get("device_type", "").upper()
                
                # Skip EMS devices - EMS rules are site-level only, not assigned to devices
                if device_type == "EMS":
                    continue
                
                # Find applicable rules for this device
                applicable_rules = []
                for rule in all_rules:
                    rule_device_types = rule.get("device_types", [])
                    # Skip EMS rules - they are site-level only, not assigned to devices
                    if rule_device_types and "EMS" in rule_device_types:
                        continue
                    
                    # Check if rule applies to this device type
                    if rule_device_types and device_type not in rule_device_types:
                        continue
                    
                    # Check if rule applies to specific device IDs
                    rule_device_ids = rule.get("device_ids", [])
                    if rule_device_ids and device_id not in rule_device_ids:
                        continue
                    
                    # Rule is applicable to this device
                    applicable_rules.append(rule)
                
                device_rules_map[device_id] = {
                    "device_id": device_id,
                    "device_type": device_type,
                    "device_name": device.get("device_name", device_id),
                    "rules": applicable_rules,
                    "rules_count": len(applicable_rules),
                }
            
            # Also include rules that don't apply to specific devices (site-level rules, multi-device rules)
            unassigned_rules = []
            assigned_rule_ids = set()
            for device_rule in device_rules_map.values():
                for rule in device_rule.get("rules", []):
                    assigned_rule_ids.add(rule.get("id"))
            
            for rule in all_rules:
                rule_id = rule.get("id")
                if rule_id and rule_id not in assigned_rule_ids:
                    # This rule doesn't apply to any specific device (site-level or multi-device rule)
                    unassigned_rules.append(rule)
            
            return {
                "status": "success",
                "data": {
                    "site_id": site_id,
                    "rules": site_rules,  # Site-specific rules from database
                    "all_rules": all_rules,  # All rules (merged with global rules)
                    "total": len(site_rules),
                    "total_all": len(all_rules),
                    "devices": list(device_rules_map.values()),
                    "devices_count": len(device_rules_map),
                    "unassigned_rules": unassigned_rules,  # Rules not assigned to specific devices
                    "unassigned_count": len(unassigned_rules),
                },
            }
        except Exception as e:
            logger.error(f"Error getting site rules: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.post("/api/v1/sites/{site_id}/rules")
    async def add_site_rule(
        site_id: str,
        rule_data: Dict[str, Any],
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        query_cache = Depends(get_query_cache),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Add a rule to a specific site"""
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
            
            # Validate required fields
            if not rule_data.get("id"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Rule ID is required",
                    },
                )
            
            if not rule_data.get("condition"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Rule condition is required",
                    },
                )
            
            # Ensure rule has consistent alarm_type in metadata
            if "metadata" not in rule_data:
                rule_data["metadata"] = {}
            
            # If alarm_type is not set, generate it from rule name
            if "alarm_type" not in rule_data.get("metadata", {}):
                rule_name = rule_data.get("name", "Unknown")
                alarm_type = rule_name.lower().replace(" ", "_").replace("-", "_")
                rule_data["metadata"]["alarm_type"] = alarm_type
                logger.debug(f"Auto-generated alarm_type '{alarm_type}' from rule name '{rule_name}'")
            
            # Add rule to site
            success = site_manager.add_site_rule(site_id, rule_data)
            if not success:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Failed to add rule. Rule ID may already exist.",
                    },
                )
            
            # Reload rules in rule engine if multi-site is enabled
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            # Invalidate alarm cache to ensure fresh data
            if query_cache:
                query_cache.invalidate("alarms")
                query_cache.invalidate("alarm_stats")
            
            # Send WebSocket event to notify frontend to refresh alarm list
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                rule_id = rule_data.get('id')
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "reason": "rule_added",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
                # Also send alarm update event to trigger alarm list refresh
                await websocket_manager.broadcast(
                    EventType.ALARM_UPDATED,
                    {
                        "reason": "rule_added",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
            
            return {
                "status": "success",
                "message": f"Rule {rule_data.get('id')} added to site {site_id}",
                "data": rule_data,
            }
        except Exception as e:
            logger.error(f"Error adding rule to site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.put("/api/v1/sites/{site_id}/rules/{rule_id}")
    async def update_site_rule(
        site_id: str,
        rule_id: str,
        rule_data: Dict[str, Any],
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        query_cache = Depends(get_query_cache),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Update a rule in a specific site"""
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
            
            # Ensure rule_id matches
            rule_data["id"] = rule_id
            
            # Validate required fields
            if not rule_data.get("condition"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Rule condition is required",
                    },
                )
            
            # Ensure rule has consistent alarm_type in metadata
            if "metadata" not in rule_data:
                rule_data["metadata"] = {}
            
            # If alarm_type is not set, generate it from rule name
            if "alarm_type" not in rule_data.get("metadata", {}):
                rule_name = rule_data.get("name", "Unknown")
                alarm_type = rule_name.lower().replace(" ", "_").replace("-", "_")
                rule_data["metadata"]["alarm_type"] = alarm_type
                logger.debug(f"Auto-generated alarm_type '{alarm_type}' from rule name '{rule_name}'")
            
            success = site_manager.update_site_rule(site_id, rule_id, rule_data)
            if not success:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Rule {rule_id} not found in site {site_id}",
                    },
                )
            
            # Reload rules in rule engine if multi-site is enabled
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            # Invalidate alarm cache to ensure fresh data
            if query_cache:
                query_cache.invalidate("alarms")
                query_cache.invalidate("alarm_stats")
            
            # Send WebSocket event to notify frontend to refresh alarm list
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "reason": "rule_updated",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
                # Also send alarm update event to trigger alarm list refresh
                await websocket_manager.broadcast(
                    EventType.ALARM_UPDATED,
                    {
                        "reason": "rule_updated",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
            
            return {
                "status": "success",
                "message": f"Rule {rule_id} updated in site {site_id}",
                "data": rule_data,
            }
        except Exception as e:
            logger.error(f"Error updating rule in site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/sites/{site_id}/rules/{rule_id}")
    async def delete_site_rule(
        site_id: str,
        rule_id: str,
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        query_cache = Depends(get_query_cache),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete a rule from a specific site"""
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
            
            # Delete rule
            success = site_manager.delete_site_rule(site_id, rule_id)
            if not success:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Rule {rule_id} not found in site {site_id}",
                    },
                )
            
            # Reload rules in rule engine if multi-site is enabled
            app_state = get_app_state()
            rule_engine = app_state.get("rule_engine")
            if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                rule_engine.site_rule_manager.reload_site_rules(site_id)
            
            # Invalidate alarm cache to ensure fresh data
            if query_cache:
                query_cache.invalidate("alarms")
                query_cache.invalidate("alarm_stats")
            
            # Send WebSocket event to notify frontend to refresh alarm list
            websocket_manager = app_state.get("websocket_manager")
            if websocket_manager:
                await websocket_manager.broadcast(
                    EventType.STATS_UPDATED,
                    {
                        "reason": "rule_deleted",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
                # Also send alarm update event to trigger alarm list refresh
                await websocket_manager.broadcast(
                    EventType.ALARM_UPDATED,
                    {
                        "reason": "rule_deleted",
                        "site_id": site_id,
                        "rule_id": rule_id,
                    },
                )
            
            return {
                "status": "success",
                "message": f"Rule {rule_id} deleted from site {site_id}",
            }
        except Exception as e:
            logger.error(f"Error deleting rule from site: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
