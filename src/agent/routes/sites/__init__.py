"""
Site management API routes - Modular structure
"""
from fastapi import FastAPI

from . import basic, devices, stats, alarms, diagnostics


def register_site_routes(app: FastAPI):
    """Register all site management routes"""
    basic.register_routes(app)
    devices.register_routes(app)
    stats.register_routes(app)
    alarms.register_routes(app)
    diagnostics.register_routes(app)
