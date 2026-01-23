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
]

