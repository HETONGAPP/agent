"""
Health check and basic endpoints
"""

import logging
from typing import Optional
from fastapi import Depends
from fastapi.responses import JSONResponse

from ...collector.mock_collector import MockCollector
from ...storage.influxdb_client import InfluxDBClient
from ...mqtt import MQTTClient
from ...agent.service import AgentService
from ...agent.dependencies import (
    get_collector,
    get_influx_client,
    get_mqtt_client,
    get_agent_service,
)
from ...agent.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_health_routes(app):
    """Register health check and basic routes"""
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": "BESS Alarm Diagnostic Agent",
            "version": "1.0.0",
            "status": "running",
        }

    @app.get("/health")
    async def health(
        collector: Optional[MockCollector] = Depends(get_collector),
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        mqtt_client: Optional[MQTTClient] = Depends(get_mqtt_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
    ):
        """Health check endpoint with detailed status"""
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "services": {}
        }
        
        # Check InfluxDB
        influxdb_status = False
        influxdb_error = None
        if influx_client:
            try:
                influx_client.client.ping()
                influxdb_status = True
            except Exception as e:
                influxdb_error = str(e)
        health_status["services"]["influxdb"] = {
            "connected": influxdb_status,
            "error": influxdb_error
        }
        
        # Check MQTT
        mqtt_status = False
        mqtt_error = None
        if mqtt_client:
            try:
                mqtt_status = mqtt_client.is_connected()
            except Exception as e:
                mqtt_error = str(e)
        health_status["services"]["mqtt"] = {
            "connected": mqtt_status,
            "error": mqtt_error
        }
        
        # Check Agent Service
        agent_status = False
        agent_error = None
        if agent_service:
            try:
                agent_status = True
            except Exception as e:
                agent_error = str(e)
        health_status["services"]["agent"] = {
            "initialized": agent_status,
            "error": agent_error
        }
        
        # Check Collector
        collector_status = False
        collector_error = None
        if collector:
            try:
                collector_status = True
            except Exception as e:
                collector_error = str(e)
        health_status["services"]["collector"] = {
            "initialized": collector_status,
            "error": collector_error
        }
        
        # Determine overall status
        critical_services = ["influxdb"]
        all_critical_healthy = all(
            health_status["services"].get(svc, {}).get("connected", False) or
            health_status["services"].get(svc, {}).get("initialized", False)
            for svc in critical_services
        )
        
        if not all_critical_healthy:
            health_status["status"] = "degraded"
            return JSONResponse(
                status_code=503,
                content=health_status
            )
        
        return health_status

