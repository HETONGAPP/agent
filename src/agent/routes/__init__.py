"""
API Routes
"""

from . import (
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
    auth,
)

__all__ = [
    "health",
    "legacy",
    "devices",
    "alarms",
    "sites",
    "sites_rules",
    "diagnostics",
    "metrics",
    "admin",
    "websocket",
    "auth",
]

