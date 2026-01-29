"""
Alarm management API routes
"""
import logging
import concurrent.futures
from collections import defaultdict
from typing import Optional
from fastapi import Depends, Query
from fastapi.responses import JSONResponse

from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.site_manager import SiteManager
from ...agent.dependencies import (
    get_influx_client,
    get_agent_service,
    get_site_manager,
    get_postgres_metadata_storage,
)
from ...agent.rate_limiter import rate_limit_dependency
from ...agent.websocket_manager import WebSocketManager, EventType

logger = logging.getLogger(__name__)

# Severity priority mapping
SEVERITY_PRIORITY = {"Critical": 3, "Warning": 2, "Info": 1, "Unknown": 0}


def normalize_severity(severity: str) -> str:
    """Normalize severity value to standard format"""
    if not severity:
        return "Unknown"
    sev = severity.strip()
    sev_lower = sev.lower()
    if sev_lower in ["critical", "crit"]:
        return "Critical"
    elif sev_lower in ["warning", "warn"]:
        return "Warning"
    elif sev_lower in ["info", "information"]:
        return "Info"
    else:
        return sev  # Keep as-is if already standard


def deduplicate_site_summaries(site_summaries: list) -> list:
    """Deduplicate site summaries, keeping the best entry per site_id"""
    if not site_summaries:
        return []
    
    summaries_dict = {}
    for summary in site_summaries:
        site_id = str(summary.get("site_id", ""))
        if not site_id:
            continue
        
        existing = summaries_dict.get(site_id)
        if not existing:
            summaries_dict[site_id] = summary
        else:
            # Compare and keep the better one
            existing_priority = SEVERITY_PRIORITY.get(existing.get("severity", "Unknown"), 0)
            new_priority = SEVERITY_PRIORITY.get(summary.get("severity", "Unknown"), 0)
            
            if new_priority > existing_priority:
                summaries_dict[site_id] = summary
            elif new_priority == existing_priority:
                # Same severity, prefer later timestamp or more alarms
                existing_time = existing.get("timestamp", "")
                new_time = summary.get("timestamp", "")
                existing_total = existing.get("total_alarms", 0)
                new_total = summary.get("total_alarms", 0)
                
                if new_time > existing_time or (new_time == existing_time and new_total > existing_total):
                    summaries_dict[site_id] = summary
    
    return list(summaries_dict.values())


def enrich_site_info(summaries: list, site_manager: Optional[SiteManager]) -> list:
    """Enrich summaries with site_name and location from site_manager"""
    if not site_manager:
        # Fallback: use site_id as site_name
        for summary in summaries:
            site_id = summary.get("site_id")
            if site_id and not summary.get("site_name"):
                summary["site_name"] = str(site_id)
            if not summary.get("location"):
                summary["location"] = ""
        return summaries
    
    for summary in summaries:
        site_id = summary.get("site_id")
        if not site_id:
            continue
        
        site_id_str = str(site_id)
        try:
            site_info = site_manager.get_site(site_id_str)
            if site_info:
                summary["site_name"] = site_info.get("site_name", site_id_str)
                summary["location"] = site_info.get("location", "")
            else:
                summary["site_name"] = site_id_str
                summary["location"] = ""
        except Exception as e:
            logger.debug(f"Failed to get site info for {site_id_str}: {e}")
            summary["site_name"] = site_id_str
            summary["location"] = ""
    
    return summaries


def register_alarm_routes(app):
    """Register alarm management routes"""

    @app.get("/api/v1/alarms")
    async def list_alarms(
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
        alarm_type: Optional[str] = None,
        severity: Optional[str] = None,
        site_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        aggregate_by_site: Optional[bool] = Query(False, description="Aggregate alarms by site"),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """
        List alarms with optional filters and pagination
        If aggregate_by_site is True and site_id is not provided, returns site-level summary
        """
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Query database directly - no caching to ensure fresh data
            alarms = []
            total_count = 0
            
            # Use site container if available
            if agent_service and agent_service.container_manager:
                if site_id:
                    # Query specific site container
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container:
                        all_site_alarms = container.query_alarms(
                            start_time=start_time,
                            end_time=end_time,
                            alarm_type=alarm_type,
                            severity=severity,
                            device_type=device_type,
                            limit=10000,
                        )
                        total_count = len(all_site_alarms)
                        all_site_alarms.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                        alarms = all_site_alarms[offset:offset + limit]
                    else:
                        alarms = []
                        total_count = 0
                else:
                    # No site_id provided
                    if aggregate_by_site:
                        # Return site-level summary
                        # Get sites from site_manager first, then check containers
                        site_ids = []
                        if site_manager:
                            try:
                                all_sites = site_manager.get_all_sites()
                                site_ids = [site.get("site_id") for site in all_sites if site.get("site_id")]
                            except Exception as e:
                                logger.warning(f"Failed to get sites from site_manager: {e}")
                        
                        # Also get containers as fallback
                        all_containers = []
                        if agent_service and agent_service.container_manager:
                            try:
                                all_containers = agent_service.container_manager.list_containers()
                            except Exception as e:
                                logger.warning(f"Failed to get containers: {e}")
                        
                        # Merge site_ids and containers, remove duplicates
                        all_site_ids = list(dict.fromkeys([str(sid) for sid in site_ids + all_containers if sid]))
                        site_summaries = []
                        
                        def query_container_alarm_summary(container_site_id: str):
                            try:
                                container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                                if not container:
                                    return None
                                
                                alarms = container.query_alarms(
                                    start_time=start_time or "-24h",
                                    end_time=end_time,
                                    alarm_type=alarm_type,
                                    severity=severity,
                                    device_type=device_type,
                                    limit=1000,
                                )
                                
                                if not alarms:
                                    return None
                                
                                # Count alarms by severity
                                severity_counts = defaultdict(int)
                                all_severities = []
                                for alarm in alarms:
                                    sev = normalize_severity(alarm.get("severity", "Unknown"))
                                    severity_counts[sev] += 1
                                    all_severities.append(sev)
                                
                                # Find highest severity
                                highest_severity = "Info"
                                highest_priority = 0
                                for sev in all_severities:
                                    priority = SEVERITY_PRIORITY.get(sev, 0)
                                    if priority > highest_priority:
                                        highest_priority = priority
                                        highest_severity = sev
                                
                                latest_alarm_time = max([a.get("timestamp", "") for a in alarms], default="")
                                
                                return {
                                    "alarm_id": f"site_{container_site_id}_summary",
                                    "alarm_type": f"Site Alarm Summary ({len(alarms)} alarms)",
                                    "severity": highest_severity,
                                    "source": "System",
                                    "site_id": container_site_id,
                                    "timestamp": latest_alarm_time,
                                    "alarm_level": "site_level",
                                    "total_alarms": len(alarms),
                                    "by_severity": dict(severity_counts),
                                }
                            except Exception as e:
                                logger.warning(f"Failed to query alarms from container {container_site_id}: {e}")
                                return None
                        
                        # Execute queries in parallel (only if there are site_ids)
                        if all_site_ids:
                            max_workers = min(5, len(all_site_ids))
                            # Ensure max_workers is at least 1
                            max_workers = max(1, max_workers)
                            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                                futures = {executor.submit(query_container_alarm_summary, sid): sid for sid in all_site_ids}
                                for future in concurrent.futures.as_completed(futures):
                                    try:
                                        result = future.result()
                                        if result:
                                            site_id_val = result.get("site_id")
                                            if site_id_val:
                                                result["site_id"] = str(site_id_val)
                                            site_summaries.append(result)
                                    except Exception as e:
                                        site_id = futures[future]
                                        logger.warning(f"Failed to query alarm summary from site {site_id}: {e}")
                        else:
                            logger.debug("No sites found for alarm aggregation")
                        
                        # Deduplicate
                        site_summaries = deduplicate_site_summaries(site_summaries)
                        
                        # Enrich with site information
                        site_summaries = enrich_site_info(site_summaries, site_manager)
                        
                        # Final deduplication after enrichment
                        site_summaries = deduplicate_site_summaries(site_summaries)
                        
                        # Sort by severity priority, then timestamp
                        site_summaries.sort(
                            key=lambda x: (
                                SEVERITY_PRIORITY.get(x.get("severity", "Unknown"), 0),
                                x.get("timestamp", "")
                            ),
                            reverse=True
                        )
                        
                        # Final deduplication after sorting
                        final_dict = {}
                        for summary in site_summaries:
                            site_id_str = str(summary.get("site_id", ""))
                            if site_id_str and site_id_str not in final_dict:
                                final_dict[site_id_str] = summary
                        
                        site_summaries = list(final_dict.values())
                        total_count = len(site_summaries)
                        alarms = site_summaries[offset:offset + limit]
                    else:
                        # Query all containers and merge results
                        all_containers = agent_service.container_manager.list_containers()
                        all_alarms = []
                        
                        def query_container_alarms(container_site_id: str):
                            try:
                                container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                                if container:
                                    return container.query_alarms(
                                        start_time=start_time,
                                        end_time=end_time,
                                        alarm_type=alarm_type,
                                        severity=severity,
                                        device_type=device_type,
                                        limit=10000,
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to query alarms from container {container_site_id}: {e}")
                            return []
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                            futures = {executor.submit(query_container_alarms, cid): cid for cid in all_containers}
                            for future in concurrent.futures.as_completed(futures):
                                try:
                                    result = future.result()
                                    if isinstance(result, list):
                                        all_alarms.extend(result)
                                except Exception as e:
                                    container_id = futures[future]
                                    logger.warning(f"Failed to query alarms from container {container_id}: {e}")
                        
                        # Filter alarms: only show site_level and system_level alarms in global view
                        filtered_alarms = []
                        for alarm in all_alarms:
                            alarm_level = alarm.get("alarm_level", "device_level")
                            if alarm.get("site_id") and alarm_level == "device_level":
                                filtered_alarms.append(alarm)
                            elif alarm_level in ["site_level", "system_level"]:
                                filtered_alarms.append(alarm)
                        
                        filtered_alarms.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                        total_count = len(filtered_alarms)
                        alarms = filtered_alarms[offset:offset + limit]
            else:
                # Fallback to legacy mode
                all_alarms = influx_client.query_alarms(
                    start_time=start_time,
                    end_time=end_time,
                    alarm_type=alarm_type,
                    severity=severity,
                    site_id=site_id,
                    device_type=device_type,
                    limit=10000,
                )
                
                filtered_alarms = []
                for alarm in all_alarms:
                    alarm_level = alarm.get("alarm_level", "device_level")
                    if alarm.get("site_id") and alarm_level == "device_level":
                        filtered_alarms.append(alarm)
                    elif alarm_level in ["site_level", "system_level"]:
                        filtered_alarms.append(alarm)
                
                total_count = len(filtered_alarms)
                alarms = filtered_alarms[offset:offset + limit]
            
            # Final validation: if aggregate_by_site, ensure no duplicate site_ids
            if aggregate_by_site and alarms:
                seen_site_ids = set()
                unique_alarms = []
                for alarm in alarms:
                    site_id_val = str(alarm.get("site_id", ""))
                    if site_id_val:
                        if site_id_val not in seen_site_ids:
                            seen_site_ids.add(site_id_val)
                            unique_alarms.append(alarm)
                    else:
                        unique_alarms.append(alarm)
                
                if len(unique_alarms) != len(alarms):
                    logger.warning(f"Removed {len(alarms) - len(unique_alarms)} duplicate site entries")
                    alarms = unique_alarms
                    total_count = len(unique_alarms)
            
            result = {
                "alarms": alarms,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
            
            # No caching - always return fresh data from database
            
            return {
                "status": "success",
                "data": result,
            }
        except Exception as e:
            logger.error(f"Error listing alarms: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/alarms/stats")
    async def get_alarm_stats(
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get alarm statistics"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            cache_params = {
                "start_time": start_time,
                "end_time": end_time,
            }
            
            # No caching - query database directly
            
            # Query alarms
            alarms = []
            if agent_service and agent_service.container_manager:
                all_containers = agent_service.container_manager.list_containers()
                
                def query_container_alarms_for_stats(container_site_id: str):
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            return container.query_alarms(
                                start_time=start_time,
                                end_time=end_time,
                                limit=10000,
                            )
                    except Exception as e:
                        logger.warning(f"Failed to query alarms from container {container_site_id} for stats: {e}")
                    return []
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(query_container_alarms_for_stats, cid): cid for cid in all_containers}
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            if isinstance(result, list):
                                alarms.extend(result)
                        except Exception as e:
                            container_id = futures[future]
                            logger.warning(f"Failed to query alarms from container {container_id} for stats: {e}")
            else:
                alarms = influx_client.query_alarms(
                    start_time=start_time,
                    end_time=end_time,
                    limit=10000,
                )
            
            # Count by severity
            severity_counts = {}
            for alarm in alarms:
                severity = alarm.get("severity", "Unknown")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by alarm type
            type_counts = {}
            for alarm in alarms:
                alarm_type = alarm.get("alarm_type", "Unknown")
                type_counts[alarm_type] = type_counts.get(alarm_type, 0) + 1
            
            # Count by source
            source_counts = {}
            for alarm in alarms:
                source = alarm.get("source", "Unknown")
                source_counts[source] = source_counts.get(source, 0) + 1
            
            result = {
                "total": len(alarms),
                "by_severity": severity_counts,
                "by_type": type_counts,
                "by_source": source_counts,
            }
            
            # No caching - always return fresh data from database
            
            return {
                "status": "success",
                "data": result,
            }
        except Exception as e:
            logger.error(f"Error getting alarm stats: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/alarms/{alarm_id}")
    async def get_alarm(
        alarm_id: str,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get alarm details by ID"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            alarms = []
            diagnostics = []
            
            if agent_service and agent_service.container_manager:
                all_containers = agent_service.container_manager.list_containers()
                for container_site_id in all_containers:
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            container_alarms = container.query_alarms(alarm_id=alarm_id, limit=1)
                            if container_alarms:
                                alarms = container_alarms
                                container_diagnostics = container.query_diagnostics(alarm_id=alarm_id, limit=1)
                                if container_diagnostics:
                                    diagnostics = container_diagnostics
                                break
                    except Exception as e:
                        logger.debug(f"Failed to query alarm from container {container_site_id}: {e}")
                        continue
            else:
                alarms = influx_client.query_alarms(
                    alarm_id=alarm_id,
                    limit=1,
                )
                if alarms:
                    diagnostics = influx_client.query_diagnostics(
                        alarm_id=alarm_id,
                        limit=1,
                    )
            
            if not alarms:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Alarm not found: {alarm_id}",
                    },
                )
            
            alarm = alarms[0]
            if diagnostics:
                alarm["diagnostic"] = diagnostics[0]
            
            return {
                "status": "success",
                "data": alarm,
            }
        except Exception as e:
            logger.error(f"Error getting alarm: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.post("/api/v1/alarms/{alarm_id}/diagnostic")
    async def generate_alarm_diagnostic(
        alarm_id: str,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Generate diagnostic report for an alarm"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Find alarm first
            alarms = []
            if agent_service and agent_service.container_manager:
                all_containers = agent_service.container_manager.list_containers()
                for container_site_id in all_containers:
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            container_alarms = container.query_alarms(alarm_id=alarm_id, limit=1)
                            if container_alarms:
                                alarms = container_alarms
                                break
                    except Exception as e:
                        logger.debug(f"Failed to query alarm from container {container_site_id}: {e}")
                        continue
            else:
                alarms = influx_client.query_alarms(alarm_id=alarm_id, limit=1)
            
            if not alarms:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Alarm not found: {alarm_id}",
                    },
                )
            
            alarm_dict = alarms[0]
            from ...models.alarm import Alarm
            from ...models.device_data import DeviceData
            alarm = Alarm.from_dict(alarm_dict)
            
            # Get device data if available
            device_data = None
            if alarm.metadata and alarm.metadata.get("device_id"):
                device_id = alarm.metadata["device_id"]
                if agent_service and agent_service.device_registry:
                    device = agent_service.device_registry.get_device(device_id)
                    if device:
                        # Get latest device data
                        if agent_service.container_manager:
                            container = agent_service.container_manager.get_container(
                                alarm.metadata.get("site_id"), auto_create=False
                            )
                            if container:
                                device_data_list = container.query_device_data(
                                    device_id=device_id, limit=1
                                )
                                if device_data_list:
                                    device_data = DeviceData.from_dict(device_data_list[0])
                        if not device_data:
                            device_data_list = influx_client.query_device_data(
                                device_id=device_id, limit=1
                            )
                            if device_data_list:
                                device_data = DeviceData.from_dict(device_data_list[0])
            
            # Generate diagnostic using LLM service
            if not agent_service or not agent_service.llm_diagnostic_service:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "error",
                        "message": "LLM diagnostic service not available",
                    },
                )
            
            llm_service = agent_service.llm_diagnostic_service
            diagnostic_report = await llm_service.generate_diagnostic(
                alarm=alarm,
                device_data=device_data,
                rule=None,
            )
            
            # Store diagnostic to InfluxDB
            site_id = alarm.metadata.get("site_id") if alarm.metadata else None
            logger.info(f"[generate_alarm_diagnostic] Generated diagnostic for alarm {alarm_id}, site_id={site_id}")
            if influx_client:
                try:
                    if agent_service and agent_service.container_manager and site_id:
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            # Convert to dict and add metadata
                            diagnostic_dict = diagnostic_report.to_dict()
                            if "metadata" not in diagnostic_dict:
                                diagnostic_dict["metadata"] = {}
                            if alarm.metadata:
                                if alarm.metadata.get("device_id"):
                                    diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                                if alarm.metadata.get("device_type"):
                                    diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                            diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                            if site_id:
                                diagnostic_dict["metadata"]["site_id"] = site_id
                            # Ensure timestamp is set for InfluxDB
                            if "timestamp" not in diagnostic_dict:
                                from datetime import datetime, UTC
                                diagnostic_dict["timestamp"] = datetime.now(UTC)
                            container.write_diagnostic(alarm.alarm_id, diagnostic_dict)
                            container.influx_client.flush()
                            logger.info(f"[generate_alarm_diagnostic] Successfully stored diagnostic to container for site {site_id}")
                            
                            # Also save to PostgreSQL for metadata storage
                            if postgres_storage:
                                try:
                                    # Prepare diagnostic data for PostgreSQL
                                    diagnostic_metadata = {
                                        "alarm_id": alarm.alarm_id,
                                        "risk_level": diagnostic_dict.get("risk_level", "Unknown"),
                                        "diagnostic_name": diagnostic_dict.get("diagnostic_name", ""),
                                        "metadata": diagnostic_dict.get("metadata", {}),
                                    }
                                    # Extract site_id, device_id, device_type, alarm_type from metadata if available
                                    if "metadata" in diagnostic_dict:
                                        metadata = diagnostic_dict["metadata"]
                                        if metadata.get("site_id"):
                                            diagnostic_metadata["site_id"] = metadata["site_id"]
                                        if metadata.get("device_id"):
                                            diagnostic_metadata["device_id"] = metadata["device_id"]
                                        if metadata.get("device_type"):
                                            diagnostic_metadata["device_type"] = metadata["device_type"]
                                        if metadata.get("alarm_type"):
                                            diagnostic_metadata["alarm_type"] = metadata["alarm_type"]
                                    elif site_id:
                                        diagnostic_metadata["site_id"] = site_id
                                    
                                    # Set timestamp
                                    if "timestamp" in diagnostic_dict:
                                        diagnostic_metadata["generated_at"] = diagnostic_dict["timestamp"]
                                    
                                    success = postgres_storage.save_diagnostic(diagnostic_metadata)
                                    if success:
                                        logger.info(f"Saved diagnostic {alarm.alarm_id} to PostgreSQL")
                                    else:
                                        logger.warning(f"Failed to save diagnostic {alarm.alarm_id} to PostgreSQL")
                                except Exception as e:
                                    logger.warning(f"Failed to save diagnostic to PostgreSQL: {e}")
                        else:
                            # Fallback to direct influx_client
                            diagnostic_dict = diagnostic_report.to_dict()
                            if "metadata" not in diagnostic_dict:
                                diagnostic_dict["metadata"] = {}
                            if alarm.metadata:
                                if alarm.metadata.get("device_id"):
                                    diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                                if alarm.metadata.get("device_type"):
                                    diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                            diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                            # Ensure timestamp is set for InfluxDB
                            if "timestamp" not in diagnostic_dict:
                                from datetime import datetime, UTC
                                diagnostic_dict["timestamp"] = datetime.now(UTC)
                            influx_client.write_diagnostic(alarm.alarm_id, diagnostic_dict, site_id=site_id, flush=True)
                            logger.info(f"[generate_alarm_diagnostic] Successfully stored diagnostic to InfluxDB (fallback) for site {site_id}")
                            
                            # Also save to PostgreSQL for metadata storage
                            if postgres_storage:
                                try:
                                    # Prepare diagnostic data for PostgreSQL
                                    diagnostic_metadata = {
                                        "alarm_id": alarm.alarm_id,
                                        "risk_level": diagnostic_dict.get("risk_level", "Unknown"),
                                        "diagnostic_name": diagnostic_dict.get("diagnostic_name", ""),
                                        "metadata": diagnostic_dict.get("metadata", {}),
                                    }
                                    # Extract site_id, device_id, device_type, alarm_type from metadata if available
                                    if "metadata" in diagnostic_dict:
                                        metadata = diagnostic_dict["metadata"]
                                        if metadata.get("site_id"):
                                            diagnostic_metadata["site_id"] = metadata["site_id"]
                                        if metadata.get("device_id"):
                                            diagnostic_metadata["device_id"] = metadata["device_id"]
                                        if metadata.get("device_type"):
                                            diagnostic_metadata["device_type"] = metadata["device_type"]
                                        if metadata.get("alarm_type"):
                                            diagnostic_metadata["alarm_type"] = metadata["alarm_type"]
                                    elif site_id:
                                        diagnostic_metadata["site_id"] = site_id
                                    
                                    # Set timestamp
                                    if "timestamp" in diagnostic_dict:
                                        diagnostic_metadata["generated_at"] = diagnostic_dict["timestamp"]
                                    
                                    success = postgres_storage.save_diagnostic(diagnostic_metadata)
                                    if success:
                                        logger.info(f"Saved diagnostic {alarm.alarm_id} to PostgreSQL")
                                    else:
                                        logger.warning(f"Failed to save diagnostic {alarm.alarm_id} to PostgreSQL")
                                except Exception as e:
                                    logger.warning(f"Failed to save diagnostic to PostgreSQL: {e}")
                    else:
                        # Direct influx_client
                        diagnostic_dict = diagnostic_report.to_dict()
                        if "metadata" not in diagnostic_dict:
                            diagnostic_dict["metadata"] = {}
                        if alarm.metadata:
                            if alarm.metadata.get("device_id"):
                                diagnostic_dict["metadata"]["device_id"] = alarm.metadata["device_id"]
                            if alarm.metadata.get("device_type"):
                                diagnostic_dict["metadata"]["device_type"] = alarm.metadata["device_type"]
                        diagnostic_dict["metadata"]["alarm_type"] = alarm.alarm_type
                        # Ensure timestamp is set for InfluxDB
                        if "timestamp" not in diagnostic_dict:
                            from datetime import datetime, UTC
                            diagnostic_dict["timestamp"] = datetime.now(UTC)
                        influx_client.write_diagnostic(alarm.alarm_id, diagnostic_dict, site_id=site_id, flush=True)
                        logger.info(f"[generate_alarm_diagnostic] Successfully stored diagnostic to InfluxDB (direct) for site {site_id}")
                    
                    # Also save to PostgreSQL for metadata storage
                    if postgres_storage:
                        try:
                            # Prepare diagnostic data for PostgreSQL
                            diagnostic_metadata = {
                                "alarm_id": alarm.alarm_id,
                                "risk_level": diagnostic_dict.get("risk_level", "Unknown"),
                                "diagnostic_name": diagnostic_dict.get("diagnostic_name", ""),
                                "metadata": diagnostic_dict.get("metadata", {}),
                            }
                            # Extract site_id, device_id, device_type, alarm_type from metadata if available
                            if "metadata" in diagnostic_dict:
                                metadata = diagnostic_dict["metadata"]
                                if metadata.get("site_id"):
                                    diagnostic_metadata["site_id"] = metadata["site_id"]
                                if metadata.get("device_id"):
                                    diagnostic_metadata["device_id"] = metadata["device_id"]
                                if metadata.get("device_type"):
                                    diagnostic_metadata["device_type"] = metadata["device_type"]
                                if metadata.get("alarm_type"):
                                    diagnostic_metadata["alarm_type"] = metadata["alarm_type"]
                            elif site_id:
                                diagnostic_metadata["site_id"] = site_id
                            
                            # Set timestamp
                            if "timestamp" in diagnostic_dict:
                                diagnostic_metadata["generated_at"] = diagnostic_dict["timestamp"]
                            
                            success = postgres_storage.save_diagnostic(diagnostic_metadata)
                            if success:
                                logger.info(f"Saved diagnostic {alarm.alarm_id} to PostgreSQL")
                            else:
                                logger.warning(f"Failed to save diagnostic {alarm.alarm_id} to PostgreSQL")
                        except Exception as e:
                            logger.warning(f"Failed to save diagnostic to PostgreSQL: {e}")
                except Exception as e:
                    logger.error(f"Failed to store diagnostic: {e}", exc_info=True)
            
            # Broadcast diagnostic_created event via WebSocket
            from ...agent.dependencies import get_app_state
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager") if app_state else None
            if websocket_manager:
                try:
                    diagnostic_dict = diagnostic_report.to_dict() if hasattr(diagnostic_report, 'to_dict') else diagnostic_report
                    site_id = alarm.metadata.get("site_id") if alarm.metadata else None
                    await websocket_manager.broadcast(
                        EventType.DIAGNOSTIC_CREATED,
                        {
                            "alarm_id": alarm.alarm_id,
                            "site_id": site_id,
                            "id": alarm.alarm_id,
                            "diagnostic": diagnostic_dict,
                        }
                    )
                    logger.info(f"Broadcasted diagnostic_created event for {alarm.alarm_id}")
                except Exception as e:
                    logger.warning(f"Failed to broadcast diagnostic_created event: {e}")
            
            return {
                "status": "success",
                "message": f"Diagnostic report generated for alarm {alarm_id}",
                "data": diagnostic_report.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error generating diagnostic: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
