"""
Agent main service - FastAPI application (refactored)
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Pre-configure logging filter for WebSocket messages
import logging
from ..utils.logging_config import WebSocketConnectionFilter  # noqa: E402

_uvicorn_access_logger = logging.getLogger("uvicorn.access")
_uvicorn_protocols_ws_logger = logging.getLogger("uvicorn.protocols.websockets")
_uvicorn_error_logger = logging.getLogger("uvicorn.error")

_uvicorn_protocols_ws_logger.setLevel(logging.DEBUG)

_ws_filter = WebSocketConnectionFilter()
for logger in [_uvicorn_access_logger, _uvicorn_protocols_ws_logger, _uvicorn_error_logger]:
    logger.addFilter(_ws_filter)

_root_logger = logging.getLogger()
_root_logger.addFilter(_ws_filter)

from .app_setup import lifespan  # noqa: E402
from .routes import (  # noqa: E402
    health,
    legacy,
    devices,
    alarms,
    sites,
    sites_rules,
    diagnostics,
    metrics,
    admin,
    websocket,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="BESS Alarm Diagnostic Agent",
        description="Battery Energy Storage System Alarm Diagnostic Agent API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    health.register_health_routes(app)
    legacy.register_legacy_routes(app)
    devices.register_device_routes(app)
    alarms.register_alarm_routes(app)
    sites.register_site_routes(app)
    sites_rules.register_site_rules_routes(app)
    diagnostics.register_diagnostic_routes(app)
    metrics.register_metrics_routes(app)
    admin.register_admin_routes(app)
    websocket.register_websocket_routes(app)

    return app


# Create application instance
app = create_app()
