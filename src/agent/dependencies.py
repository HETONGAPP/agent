"""
Application Dependencies
Provides dependency injection for FastAPI endpoints
"""

from typing import Optional
from fastapi import Depends

from ..collector.mock_collector import MockCollector
from ..storage.influxdb_client import InfluxDBClient
from ..agent.service import AgentService
from ..agent.websocket_manager import WebSocketManager
from ..mqtt import MQTTClient, MQTTMessageHandler
from ..core import IntegrationManager, DataCollectionService, DeviceRegistry


# Application state (initialized in lifespan)
_app_state = {
    "collector": None,
    "influx_client": None,
    "agent_service": None,
    "mqtt_client": None,
    "mqtt_handler": None,
    "integration_manager": None,
    "data_collection_service": None,
    "device_registry": None,
    "websocket_manager": None,
    "site_manager": None,
    "rule_engine": None,
    "query_cache": None,
    "event_bus": None,
}


def get_app_state():
    """Get application state dictionary"""
    return _app_state


def set_app_state(**kwargs):
    """Set application state"""
    _app_state.update(kwargs)


def get_collector() -> Optional[MockCollector]:
    """Get collector instance"""
    return _app_state.get("collector")


def get_influx_client() -> Optional[InfluxDBClient]:
    """Get InfluxDB client instance"""
    return _app_state.get("influx_client")


def get_agent_service() -> Optional[AgentService]:
    """Get agent service instance"""
    return _app_state.get("agent_service")


def get_mqtt_client() -> Optional[MQTTClient]:
    """Get MQTT client instance"""
    return _app_state.get("mqtt_client")


def get_mqtt_handler() -> Optional[MQTTMessageHandler]:
    """Get MQTT handler instance"""
    return _app_state.get("mqtt_handler")


def get_integration_manager() -> Optional[IntegrationManager]:
    """Get integration manager instance"""
    return _app_state.get("integration_manager")


def get_data_collection_service() -> Optional[DataCollectionService]:
    """Get data collection service instance"""
    return _app_state.get("data_collection_service")


def get_device_registry() -> Optional[DeviceRegistry]:
    """Get device registry instance"""
    return _app_state.get("device_registry")


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get WebSocket manager instance"""
    return _app_state.get("websocket_manager")


def get_site_manager() -> Optional["SiteManager"]:
    """Get site manager instance"""
    return _app_state.get("site_manager")


def get_query_cache():
    """Get query cache instance"""
    from ..storage.query_cache import QueryCache
    return _app_state.get("query_cache")


def get_event_bus():
    """Get event bus instance"""
    from ..core.event_bus import EventBus
    return _app_state.get("event_bus")


# Dependency functions for FastAPI
def require_agent_service(agent_service: Optional[AgentService] = Depends(get_agent_service)) -> AgentService:
    """Dependency that requires agent service to be initialized"""
    if agent_service is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Agent service not initialized"
        )
    return agent_service


def require_influx_client(influx_client: Optional[InfluxDBClient] = Depends(get_influx_client)) -> InfluxDBClient:
    """Dependency that requires InfluxDB client to be initialized"""
    if influx_client is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="InfluxDB client not initialized"
        )
    return influx_client

