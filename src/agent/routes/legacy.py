"""
Legacy API endpoints (for backward compatibility)
"""

import logging
from typing import Optional
from fastapi import Request, Depends
from fastapi.responses import JSONResponse

from ...collector.mock_collector import MockCollector
from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.webhook_auth import verify_webhook_auth
from ...agent.webhook_models import WebhookResponse
from ...agent.dependencies import (
    get_collector,
    get_influx_client,
    require_agent_service,
)
from ...agent.rate_limiter import rate_limit_dependency
from ...grafana import GrafanaWebhookHandler

logger = logging.getLogger(__name__)


def register_legacy_routes(app):
    """Register legacy API routes"""
    
    @app.post("/api/collect")
    async def collect_data(
        collector: Optional[MockCollector] = Depends(get_collector),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Collect data and write to InfluxDB"""
        if not collector:
            return JSONResponse(
                status_code=503, content={"status": "error", "message": "Collector not initialized"}
            )
        
        try:
            alarms = await collector.collect_alarms()
            bms_data = await collector.get_bms_data("PACK_001")

            if influx_client:
                for alarm in alarms:
                    influx_client.write_alarm(alarm)
                influx_client.write_bms_data(bms_data)

            return {
                "status": "success",
                "alarms_count": len(alarms),
                "bms_data": bms_data.to_dict(),
                "influxdb_written": influx_client is not None,
            }
        except Exception as e:
            logger.error(f"Error collecting data: {e}", exc_info=True)
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(e)}
            )

    @app.get("/api/alarms")
    async def get_alarms(
        collector: Optional[MockCollector] = Depends(get_collector),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get latest alarms"""
        if not collector:
            return JSONResponse(
                status_code=503, content={"status": "error", "message": "Collector not initialized"}
            )
        
        try:
            alarms = await collector.collect_alarms()
            return {
                "status": "success",
                "alarms": [alarm.to_dict() for alarm in alarms],
            }
        except Exception as e:
            logger.error(f"Error getting alarms: {e}", exc_info=True)
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(e)}
            )

    @app.get("/api/bms-data")
    async def get_bms_data(
        pack_id: str = "PACK_001",
        collector: Optional[MockCollector] = Depends(get_collector),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get BMS data"""
        if not collector:
            return JSONResponse(
                status_code=503, content={"status": "error", "message": "Collector not initialized"}
            )
        
        try:
            bms_data = await collector.get_bms_data(pack_id)
            return {
                "status": "success",
                "bms_data": bms_data.to_dict(),
            }
        except Exception as e:
            logger.error(f"Error getting BMS data: {e}", exc_info=True)
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(e)}
            )

    @app.post("/api/webhook/grafana", response_model=WebhookResponse)
    async def grafana_webhook(
        request: Request,
        authenticated: bool = Depends(verify_webhook_auth),
        agent_service: AgentService = Depends(require_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """
        Receive Grafana alert webhook
        Process alarm, generate diagnostic, and create annotation
        """
        try:
            raw_payload = await request.json()
            handler = GrafanaWebhookHandler(agent_service)
            result = await handler.handle_webhook(raw_payload)
            return result
        except Exception as e:
            logger.error(f"Error processing Grafana webhook: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )

