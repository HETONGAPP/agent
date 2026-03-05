"""
Settings API routes
GET /api/v1/settings/llm - current LLM config (masked).
GET /api/v1/settings/infrastructure - Redis, InfluxDB, MQTT, PostgreSQL (masked).
PUT /api/v1/settings/infrastructure - save overrides (takes effect on restart).
"""

import logging
import yaml
from pathlib import Path

from fastapi import Body
from fastapi.responses import JSONResponse

from ..dependencies import get_app_state

logger = logging.getLogger(__name__)

MASK = "***"


def _mask(s):
    """Return masked value if string is non-empty."""
    if s is None:
        return ""
    s = str(s).strip()
    return MASK if s else ""


def _merge_masked(current: dict, incoming: dict) -> dict:
    """Merge incoming into current; treat '__MASKED__' as keep existing value."""
    out = dict(current)
    for key, val in incoming.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_masked(out[key], val)
        elif val != "__MASKED__":
            out[key] = val
    return out


def register_settings_routes(app):
    """Register settings routes."""

    @app.get("/api/v1/settings/llm")
    async def get_llm_settings():
        """Return current LLM config for UI. API key is never returned."""
        app_state = get_app_state()
        config = app_state.get("config") or {}
        llm = config.get("llm") or {}
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": {
                    "provider": llm.get("provider"),
                    "model": llm.get("ollama_model") or llm.get("model"),
                    "ollama_url": llm.get("ollama_url"),
                },
            },
        )

    @app.get("/api/v1/settings/infrastructure")
    async def get_infrastructure_settings():
        """Return Redis, InfluxDB, MQTT, PostgreSQL config for UI. Passwords/tokens masked."""
        app_state = get_app_state()
        config = app_state.get("config") or {}
        db = config.get("database") or {}
        redis = db.get("redis") or {}
        influx = db.get("influxdb") or {}
        pg = db.get("postgresql") or {}
        mqtt = config.get("mqtt") or {}
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "data": {
                    "redis": {
                        "host": redis.get("host", ""),
                        "port": redis.get("port", 6379),
                        "db": redis.get("db", 0),
                        "password": _mask(redis.get("password")),
                    },
                    "influxdb": {
                        "url": influx.get("url", ""),
                        "org": influx.get("org", ""),
                        "bucket": influx.get("bucket", ""),
                        "token": _mask(influx.get("token")),
                    },
                    "postgresql": {
                        "host": pg.get("host", ""),
                        "port": pg.get("port", 5432),
                        "database": pg.get("database", ""),
                        "user": pg.get("user", ""),
                        "password": _mask(pg.get("password")),
                    },
                    "mqtt": {
                        "broker_url": mqtt.get("broker_url", ""),
                        "client_id": mqtt.get("client_id", ""),
                        "username": mqtt.get("username", ""),
                        "password": _mask(mqtt.get("password")),
                    },
                },
            },
        )

    @app.put("/api/v1/settings/infrastructure")
    async def put_infrastructure_settings(body: dict = Body(...)):
        """Save infrastructure overrides to config/infrastructure_overrides.yaml. Takes effect on agent restart. Use __MASKED__ for password/token to keep existing."""
        try:
            root = Path(__file__).resolve().parent.parent.parent
            overrides_path = root / "config" / "infrastructure_overrides.yaml"
            overrides_path.parent.mkdir(parents=True, exist_ok=True)
            current = {}
            if overrides_path.exists():
                with open(overrides_path, "r") as f:
                    current = yaml.safe_load(f) or {}
            merged = _merge_masked(current, body)
            with open(overrides_path, "w") as f:
                yaml.dump(merged, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info("Saved infrastructure overrides to config/infrastructure_overrides.yaml")
            return JSONResponse(status_code=200, content={"status": "success", "message": "Saved. Restart agent to apply."})
        except Exception as e:
            logger.exception("Failed to save infrastructure overrides")
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
