"""
Diagnostic API routes
"""
import logging
import concurrent.futures
from typing import Optional
from fastapi import Depends
from fastapi.responses import JSONResponse

from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.dependencies import (
    get_influx_client,
    get_agent_service,
    get_device_registry,
    get_query_cache,
    get_postgres_metadata_storage,
)
from ...agent.rate_limiter import rate_limit_dependency
from ...core import DeviceRegistry
from ...llm_diagnostic.client import LLMClient
from ...diagnostic_agent import (
    DiagnosticPlanner,
    DiagnosticExecutor,
    DiagnosticTaskManager,
)
from ...diagnostic_agent.agents import DataCollectorAgent, AlarmAnalyzerAgent

logger = logging.getLogger(__name__)

def register_diagnostic_routes(app):
    """Register diagnostic routes"""

    @app.get("/api/v1/diagnostics")
    async def list_diagnostics(
        alarm_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """List diagnostic reports with optional filters and pagination
        Queries both PostgreSQL (metadata) and InfluxDB (full reports) and merges results
        """
        try:
            pg_diagnostics_list = []
            
            # First, query PostgreSQL for diagnostic metadata
            if postgres_storage:
                try:
                    pg_diagnostics = postgres_storage.get_all_diagnostics(
                        site_id=site_id,
                        risk_level=risk_level,
                        limit=None,  # Get all matching records for merging
                        offset=None,
                    )
                    
                    # Filter by alarm_id if provided
                    if alarm_id:
                        pg_diagnostics = [d for d in pg_diagnostics if d.get("alarm_id") == alarm_id]
                    
                    # Convert PostgreSQL format to match InfluxDB format
                    for pg_diag in pg_diagnostics:
                        # Create diagnostic dict in InfluxDB format
                        diagnostic_dict = {
                            "alarm_id": pg_diag.get("alarm_id"),
                            "site_id": pg_diag.get("site_id"),
                            "device_id": pg_diag.get("device_id"),
                            "device_type": pg_diag.get("device_type"),
                            "alarm_type": pg_diag.get("alarm_type"),
                            "risk_level": pg_diag.get("risk_level"),
                            "current_status": pg_diag.get("current_status"),
                            "timestamp": pg_diag.get("generated_at") or pg_diag.get("created_at"),
                            "generated_at": pg_diag.get("generated_at"),
                            "metadata": pg_diag.get("metadata", {}),
                        }
                        pg_diagnostics_list.append(diagnostic_dict)
                    
                    logger.info(f"Loaded {len(pg_diagnostics_list)} diagnostics from PostgreSQL")
                except Exception as e:
                    logger.warning(f"Failed to query diagnostics from PostgreSQL: {e}")
            
            # Then query InfluxDB for full diagnostic reports
            influx_diagnostics = []
            if influx_client:
                # Use site container if available
                agent_service = get_agent_service()
                if agent_service and agent_service.container_manager:
                    if site_id:
                        # Query specific site container
                        container = agent_service.container_manager.get_container(site_id, auto_create=False)
                        if container:
                            # Query from site container (no need for site_id filter)
                            # Set deduplicate=False to show all diagnostics, not just the latest one per (device_id, alarm_type)
                            influx_diagnostics = container.query_diagnostics(
                                start_time=start_time,
                                end_time=end_time,
                                alarm_id=alarm_id,
                                risk_level=risk_level,
                                device_type=device_type,
                                limit=10000,
                                deduplicate=False,  # Show all diagnostics, not just latest
                            )
                        # If container doesn't exist, influx_diagnostics remains empty
                    else:
                        # No site_id provided, query all containers and merge results (parallel optimization)
                        all_containers = agent_service.container_manager.list_containers()
                        
                        # Parallel query optimization (query_diagnostics is sync, so we use ThreadPoolExecutor)
                        import concurrent.futures
                        
                        def query_container_diagnostics(container_site_id: str):
                            try:
                                container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                                if container:
                                    return container.query_diagnostics(
                                        start_time=start_time,
                                        end_time=end_time,
                                        alarm_id=alarm_id,
                                        risk_level=risk_level,
                                        device_type=device_type,
                                        limit=10000,
                                        deduplicate=False,  # Show all diagnostics, not just latest
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to query diagnostics from container {container_site_id}: {e}")
                            return []
                        
                        # Execute queries in parallel using thread pool
                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                            futures = {executor.submit(query_container_diagnostics, cid): cid for cid in all_containers}
                            for future in concurrent.futures.as_completed(futures):
                                try:
                                    result = future.result()
                                    if isinstance(result, list):
                                        influx_diagnostics.extend(result)
                                except Exception as e:
                                    container_id = futures[future]
                                    logger.warning(f"Failed to query diagnostics from container {container_id}: {e}")
                else:
                    # Fallback to legacy mode (query with site_id filter)
                    influx_diagnostics = influx_client.query_diagnostics(
                        start_time=start_time,
                        end_time=end_time,
                        alarm_id=alarm_id,
                        risk_level=risk_level,
                        site_id=site_id,
                        device_type=device_type,
                        limit=10000,
                    )
            
            # Merge PostgreSQL and InfluxDB results
            # Use alarm_id as unique key to deduplicate
            diagnostics_map = {}
            
            # Add InfluxDB diagnostics first (they have full report data)
            for diag in influx_diagnostics:
                alarm_id_key = diag.get("alarm_id")
                if alarm_id_key:
                    diagnostics_map[alarm_id_key] = diag
            
            # Add PostgreSQL diagnostics (they may have metadata not in InfluxDB)
            for pg_diag in pg_diagnostics_list:
                alarm_id_key = pg_diag.get("alarm_id")
                if alarm_id_key:
                    if alarm_id_key in diagnostics_map:
                        # Merge: InfluxDB has full report, PostgreSQL has metadata
                        # Update InfluxDB diagnostic with PostgreSQL metadata if missing
                        influx_diag = diagnostics_map[alarm_id_key]
                        if not influx_diag.get("site_id") and pg_diag.get("site_id"):
                            influx_diag["site_id"] = pg_diag.get("site_id")
                        if not influx_diag.get("device_id") and pg_diag.get("device_id"):
                            influx_diag["device_id"] = pg_diag.get("device_id")
                        if not influx_diag.get("device_type") and pg_diag.get("device_type"):
                            influx_diag["device_type"] = pg_diag.get("device_type")
                        if not influx_diag.get("risk_level") and pg_diag.get("risk_level"):
                            influx_diag["risk_level"] = pg_diag.get("risk_level")
                        if not influx_diag.get("current_status") and pg_diag.get("current_status"):
                            influx_diag["current_status"] = pg_diag.get("current_status")
                    else:
                        # PostgreSQL has diagnostic but InfluxDB doesn't - add it
                        diagnostics_map[alarm_id_key] = pg_diag
                        logger.debug(f"Added diagnostic from PostgreSQL only: {alarm_id_key}")
            
            # Convert map back to list and sort by timestamp (descending)
            all_diagnostics = list(diagnostics_map.values())
            all_diagnostics.sort(key=lambda x: (
                x.get("generated_at") or x.get("timestamp") or x.get("created_at") or ""
            ), reverse=True)
            
            total_count = len(all_diagnostics)
            
            # Apply offset and limit
            diagnostics = all_diagnostics[offset:offset + limit]
            
            full_diagnostics = diagnostics
            
            return {
                "status": "success",
                "data": {
                    "diagnostics": full_diagnostics,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                },
            }
        except Exception as e:
            logger.error(f"Error listing diagnostics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/diagnostics/stats")
    async def get_diagnostic_stats(
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        site_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        device_type: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        query_cache = Depends(get_query_cache),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get diagnostic report statistics with optional filters"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Check cache first (include filters in cache key)
            cache_params = {
                "start_time": start_time,
                "end_time": end_time,
                "site_id": site_id,
                "risk_level": risk_level,
                "device_type": device_type,
            }
            
            if query_cache:
                cached_result = query_cache.get("diagnostic_stats", cache_params)
                if cached_result:
                    logger.debug(f"Cache hit for diagnostic stats: {cache_params}")
                    return {
                        "status": "success",
                        "data": cached_result,
                    }
            
            # Use site container if available (same logic as list_diagnostics)
            if agent_service and agent_service.container_manager:
                # If site_id is specified, only query that container
                if site_id:
                    containers_to_query = [site_id]
                else:
                    containers_to_query = agent_service.container_manager.list_containers()
                
                all_diagnostics = []
                
                def query_container_diagnostics_for_stats(container_site_id: str):
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            # Limit to 500 per container for stats (much faster than 10000)
                            # Statistics don't need all records, just enough for accurate counts
                            # Disable deduplication for stats to get accurate counts
                            return container.query_diagnostics(
                                start_time=start_time,
                                end_time=end_time,
                                risk_level=risk_level,
                                device_type=device_type,
                                limit=500,  # Reduced from 10000 for better performance
                                deduplicate=False,  # Don't deduplicate for stats - we want accurate counts
                            )
                    except Exception as e:
                        logger.warning(f"Failed to query diagnostics from container {container_site_id} for stats: {e}")
                    return []
                
                # Use concurrent queries for better performance
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(query_container_diagnostics_for_stats, cid): cid for cid in containers_to_query}
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            if isinstance(result, list):
                                all_diagnostics.extend(result)
                        except Exception as e:
                            container_id = futures[future]
                            logger.warning(f"Failed to query diagnostics from container {container_id} for stats: {e}")
                
                diagnostics = all_diagnostics
            else:
                # Fallback to legacy mode - also reduce limit for better performance
                diagnostics = influx_client.query_diagnostics(
                    start_time=start_time,
                    end_time=end_time,
                    risk_level=risk_level,
                    site_id=site_id,
                    device_type=device_type,
                    limit=500,  # Reduced from 10000 for better performance
                )
            
            # Count by risk level
            risk_level_counts = {}
            for diag in diagnostics:
                risk_level = diag.get("risk_level", "Unknown")
                risk_level_counts[risk_level] = risk_level_counts.get(risk_level, 0) + 1
            
            result = {
                "total": len(diagnostics),
                "by_risk_level": risk_level_counts,
            }
            
            # Cache the result for 5 minutes (300 seconds) to reduce database queries
            # Stats don't need to be real-time, 5 minutes is acceptable
            if query_cache:
                query_cache.set("diagnostic_stats", cache_params, result, ttl=300)
                logger.debug(f"Cached diagnostic stats with TTL=300s: {cache_params}")
            
            return {
                "status": "success",
                "data": result,
            }
        except Exception as e:
            logger.error(f"Error getting diagnostic stats: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/diagnostics/{alarm_id}")
    async def get_diagnostic_by_alarm(
        alarm_id: str,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get diagnostic report for a specific alarm"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Try to get site_id from alarm first (if available)
            site_id = None
            if agent_service and agent_service.container_manager:
                # Try to find alarm in any container to get site_id
                all_containers = agent_service.container_manager.list_containers()
                for container_site_id in all_containers:
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            alarms = container.query_alarms(alarm_id=alarm_id, limit=1)
                            if alarms and len(alarms) > 0:
                                site_id = container_site_id
                                break
                    except Exception as e:
                        logger.debug(f"Failed to query alarm from container {container_site_id} for site_id: {e}")
                        continue
            
            # Use site container if available
            if agent_service and agent_service.container_manager:
                if site_id:
                    # Query specific site container
                    container = agent_service.container_manager.get_container(site_id, auto_create=False)
                    if container:
                        diagnostics = container.query_diagnostics(
                            alarm_id=alarm_id,
                            limit=1,
                        )
                    else:
                        diagnostics = []
                else:
                    # No site_id found, query all containers and merge results
                    all_containers = agent_service.container_manager.list_containers()
                    diagnostics = []
                    for container_site_id in all_containers:
                        try:
                            container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                            if container:
                                container_diagnostics = container.query_diagnostics(
                                    alarm_id=alarm_id,
                                    limit=1,
                                )
                                if container_diagnostics:
                                    diagnostics.extend(container_diagnostics)
                                    break
                        except Exception as e:
                            logger.warning(f"Failed to query diagnostics from container {container_site_id}: {e}")
                            continue
            else:
                # Fallback to legacy mode (query default bucket)
                diagnostics = influx_client.query_diagnostics(
                    alarm_id=alarm_id,
                    limit=1,
                )
            
            if not diagnostics:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Diagnostic report not found for alarm {alarm_id}",
                    },
                )
            
            diagnostic = diagnostics[0]
            full_diagnostic = diagnostic
            
            if agent_service and hasattr(agent_service, "llm_diagnostic_service"):
                llm_service = agent_service.llm_diagnostic_service
                if llm_service and hasattr(llm_service, "cache") and llm_service.cache:
                    try:
                        pass
                    except Exception:
                        pass
            
            return {
                "status": "success",
                "data": full_diagnostic,
            }
        except Exception as e:
            logger.error(f"Error getting diagnostic for alarm {alarm_id}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.delete("/api/v1/diagnostics/{alarm_id}")
    async def delete_diagnostic(
        alarm_id: str,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete diagnostic report for a specific alarm"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            # Try to get site_id from diagnostic first
            site_id = None
            if agent_service and agent_service.container_manager:
                # Try to find diagnostic in any container to get site_id
                all_containers = agent_service.container_manager.list_containers()
                for container_site_id in all_containers:
                    try:
                        container = agent_service.container_manager.get_container(container_site_id, auto_create=False)
                        if container:
                            diagnostics = container.query_diagnostics(alarm_id=alarm_id, limit=1)
                            if diagnostics and len(diagnostics) > 0:
                                site_id = container_site_id
                                break
                    except Exception as e:
                        logger.debug(f"Failed to query diagnostic from container {container_site_id} for site_id: {e}")
                        continue
            
            # Delete from InfluxDB
            deleted = False
            if agent_service and agent_service.container_manager and site_id:
                # Use site container
                container = agent_service.container_manager.get_container(site_id, auto_create=False)
                if container:
                    deleted = container.delete_diagnostic(alarm_id)
                else:
                    # Fallback to direct influx_client
                    deleted = influx_client.delete_diagnostic(alarm_id, site_id=site_id)
            else:
                # Direct influx_client
                deleted = influx_client.delete_diagnostic(alarm_id, site_id=site_id)
            
            # Delete from cache if available
            if agent_service and hasattr(agent_service, "llm_diagnostic_service"):
                llm_service = agent_service.llm_diagnostic_service
                if llm_service and hasattr(llm_service, "cache") and llm_service.cache:
                    try:
                        # Build context for cache key (minimal context for deletion)
                        from ...models.alarm import Alarm
                        from ...models.device import DeviceData
                        # Create a minimal alarm object for cache key generation
                        # We need alarm_id and alarm_type at minimum
                        # Try to get alarm info from InfluxDB first
                        alarms = influx_client.query_alarms(alarm_id=alarm_id, limit=1)
                        if alarms and len(alarms) > 0:
                            alarm_data = alarms[0]
                            # Build minimal context for cache deletion
                            context = {
                                "alarm_id": alarm_id,
                                "alarm_type": alarm_data.get("alarm_type", ""),
                            }
                            await llm_service.cache.delete(alarm_id, context)
                            logger.info(f"Deleted diagnostic from cache for alarm {alarm_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete diagnostic from cache: {e}")
            
            if deleted:
                return {
                    "status": "success",
                    "message": f"Diagnostic report deleted for alarm {alarm_id}",
                }
            else:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Diagnostic report not found for alarm {alarm_id}",
                    },
                )
        except Exception as e:
            logger.error(f"Error deleting diagnostic for alarm {alarm_id}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.post("/api/v1/sites/{site_id}/diagnostics/agent/start")
    async def start_diagnostic_agent(
        site_id: str,
        time_range: str = "-24h",
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Start diagnostic agent analysis for a site"""
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
        
        try:
            # Get LLM client from diagnostic service
            llm_client = agent_service.llm_diagnostic_service.llm_client
            
            # Get WebSocket manager for real-time updates
            from ...agent.dependencies import get_app_state
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager")
            
            # Generate diagnostic ID
            import time
            diagnostic_id = f"diagnostic_{site_id}_{int(time.time())}"
            
            # Create planner
            planner = DiagnosticPlanner(llm_client)
            
            # Plan diagnostic tasks
            task_manager = await planner.plan_diagnostic(
                site_id=site_id,
                time_range=time_range,
            )
            
            # Create agents
            from ...diagnostic_agent.agents import (
                DeviceAnalyzerAgent,
                TrendAnalyzerAgent,
                CorrelationAgent,
                ReportGeneratorAgent,
            )
            
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
            
            # Get final report (from last task)
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
            
            return {
                "status": "success",
                "site_id": site_id,
                "diagnostic_id": diagnostic_id,
                "task_count": len(task_manager.tasks),
                "completed_count": sum(1 for t in task_manager.tasks if t.status.value == "completed"),
                "failed_count": sum(1 for t in task_manager.tasks if t.status.value == "failed"),
                "tasks": task_manager.to_dict()["tasks"],
                "results": results,
                "final_result": final_task.result if final_task else None,
            }
            
        except Exception as e:
            logger.error(f"Error starting diagnostic agent for site {site_id}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/sites/{site_id}/diagnostics/agent/status")
    async def get_diagnostic_agent_status(
        site_id: str,
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get diagnostic agent execution status (placeholder for future WebSocket implementation)"""
        # TODO: Implement status tracking with WebSocket
        return {
            "status": "success",
            "message": "Status tracking not yet implemented. Use /start endpoint to run diagnostics.",
        }
    
    @app.post("/api/v1/diagnostics/metadata")
    async def create_diagnostic_metadata(
        diagnostic_data: dict,
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Create diagnostic metadata in PostgreSQL"""
        if not postgres_storage:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "PostgreSQL metadata storage not initialized",
                },
            )
        
        try:
            # Validate required fields
            if not diagnostic_data.get("alarm_id"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "alarm_id is required",
                    },
                )
            
            if not diagnostic_data.get("risk_level"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "risk_level is required",
                    },
                )
            
            success = postgres_storage.save_diagnostic(diagnostic_data)
            if success:
                return {
                    "status": "success",
                    "message": f"Diagnostic metadata created for alarm {diagnostic_data.get('alarm_id')}",
                }
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Failed to create diagnostic metadata",
                    },
                )
        except Exception as e:
            logger.error(f"Error creating diagnostic metadata: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": str(e),
                },
            )
    
    @app.delete("/api/v1/diagnostics/metadata/{alarm_id}")
    async def delete_diagnostic_metadata(
        alarm_id: str,
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Delete diagnostic metadata from PostgreSQL"""
        if not postgres_storage:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "PostgreSQL metadata storage not initialized",
                },
            )
        
        try:
            success = postgres_storage.delete_diagnostic(alarm_id)
            if success:
                return {
                    "status": "success",
                    "message": f"Diagnostic metadata deleted for alarm {alarm_id}",
                }
            else:
                return JSONResponse(
                    status_code=404,
                    content={
                        "status": "error",
                        "message": f"Diagnostic metadata not found for alarm {alarm_id}",
                    },
                )
        except Exception as e:
            logger.error(f"Error deleting diagnostic metadata: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": str(e),
                },
            )
    
    @app.get("/api/v1/diagnostics/metadata")
    async def list_diagnostic_metadata(
        site_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """List diagnostic metadata from PostgreSQL"""
        if not postgres_storage:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "PostgreSQL metadata storage not initialized",
                },
            )
        
        try:
            diagnostics = postgres_storage.get_all_diagnostics(
                site_id=site_id,
                risk_level=risk_level,
                limit=limit,
                offset=offset,
            )
            return {
                "status": "success",
                "data": diagnostics,
                "total": len(diagnostics),
            }
        except Exception as e:
            logger.error(f"Error listing diagnostic metadata: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": str(e),
                },
            )
    
