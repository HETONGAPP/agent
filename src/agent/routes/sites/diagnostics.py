"""
Site diagnostics routes
"""
import logging
import time
from datetime import datetime, UTC
from typing import Optional
from fastapi import Depends, FastAPI, Body
from fastapi.responses import JSONResponse

from ....core import DeviceRegistry
from ....storage.influxdb_client import InfluxDBClient
from ...service import AgentService
from ...site_manager import SiteManager
from ...websocket_manager import EventType
from ...dependencies import (
    get_site_manager,
    get_influx_client,
    get_agent_service,
    get_device_registry,
    get_postgres_metadata_storage,
    get_app_state,
)
from ...rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    """Register site diagnostics routes"""

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
    
    @app.post("/api/v1/sites/{site_id}/diagnostics/generate")
    async def generate_site_diagnostic(
        site_id: str,
        time_range: str = "-24h",
        body: Optional[dict] = Body(None),
        site_manager: Optional[SiteManager] = Depends(get_site_manager),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        device_registry: Optional[DeviceRegistry] = Depends(get_device_registry),
        postgres_storage = Depends(get_postgres_metadata_storage),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Manually trigger diagnostic agent analysis for a site. Optional body: { llm_override: { provider?, api_key?, model?, ollama_url? } }."""
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
            # LLM client: use override from request body if provided, else server default
            llm_override = (body or {}).get("llm_override") if isinstance(body, dict) else None
            if llm_override and isinstance(llm_override, dict):
                app_state = get_app_state()
                config = app_state.get("config") or {}
                base_llm = dict(config.get("llm") or {})
                base_llm.setdefault("temperature", 0.3)
                base_llm.setdefault("max_tokens", 2000)
                base_llm.setdefault("timeout", 50)
                base_llm.setdefault("retry_times", 3)
                override_clean = {k: v for k, v in llm_override.items() if v is not None and v != ""}
                merged = {**base_llm, **override_clean}
                if merged.get("provider", "").lower() == "ollama" and merged.get("model"):
                    merged["ollama_model"] = merged["model"]
                # cursor-api does not support gpt-4/gpt-4o; use "default" (Auto) when base_url is set
                if merged.get("base_url") and (merged.get("model") or "").lower() in ("gpt-4", "gpt-4o"):
                    merged["model"] = "default"
                if merged.get("provider"):
                    from ....llm_diagnostic.client import LLMClient
                    llm_client = LLMClient.from_config(merged)
                else:
                    llm_client = agent_service.llm_diagnostic_service.llm_client
            else:
                llm_client = agent_service.llm_diagnostic_service.llm_client

            # Get WebSocket manager for real-time updates
            app_state = get_app_state()
            websocket_manager = app_state.get("websocket_manager") if app_state else None
            
            # Generate diagnostic ID
            diagnostic_id = f"diagnostic_{site_id}_{int(time.time())}"
            
            # Import diagnostic agent components
            from ....diagnostic_agent.planner import DiagnosticPlanner
            from ....diagnostic_agent.executor import DiagnosticExecutor
            from ....diagnostic_agent.agents import (
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
                    from ....models.diagnostic import DiagnosticReport
                    report_dict = result.get("report")
                    if isinstance(report_dict, dict):
                        diagnostic_report = DiagnosticReport.from_dict(report_dict)
                    else:
                        diagnostic_report = report_dict
            
            # If no report found, create a fallback
            if not diagnostic_report:
                from ....models.diagnostic import DiagnosticReport, RiskLevel
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
                            diagnostic_metadata = {
                                "alarm_id": alarm_id,
                                "site_id": site_id,
                                "risk_level": diagnostic_dict.get("risk_level", "Unknown"),
                                "diagnostic_name": diagnostic_dict.get("diagnostic_name", ""),
                                "metadata": diagnostic_dict.get("metadata", {}),
                            }
                            if "metadata" in diagnostic_dict:
                                metadata = diagnostic_dict["metadata"]
                                if metadata.get("device_id"):
                                    diagnostic_metadata["device_id"] = metadata["device_id"]
                                if metadata.get("device_type"):
                                    diagnostic_metadata["device_type"] = metadata["device_type"]
                                if metadata.get("alarm_type"):
                                    diagnostic_metadata["alarm_type"] = metadata["alarm_type"]
                            
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
