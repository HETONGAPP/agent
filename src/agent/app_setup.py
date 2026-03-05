"""
Application setup and lifecycle management
"""

import logging
import os
import yaml
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI

from ..agent.service import AgentService
from ..collector.mock_collector import MockCollector
from ..core import DeviceRegistry
from ..core.integration import DeviceIntegration
from ..email import EmailService
from ..grafana import AnnotationService, GrafanaClient
from ..llm_diagnostic import LLMDiagnosticService
from ..models.device_data import DeviceType
from ..mqtt import MQTTClient, MQTTMessageHandler
from ..rule_engine import RuleEngine
from ..storage.influxdb_client import InfluxDBClient
from ..agent.config_validator import ConfigValidator
from ..agent.dependencies import get_app_state, set_app_state
from ..agent.websocket_manager import WebSocketManager, EventType
from ..agent.site_manager import SiteManager

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Merge override into base in place. Override values take precedence."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def expand_env_vars(value: Any) -> Any:
    """
    Recursively expand environment variables in configuration values.
    Supports ${VAR:-default} syntax.
    """
    import re
    
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    elif isinstance(value, str):
        pattern = r'\$\{([^:}]+)(?::-([^}]*))?\}'
        
        def replace_env(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ""
            env_value = os.getenv(var_name, default_value)
            return env_value
        
        result = re.sub(pattern, replace_env, value)
        
        if result.isdigit():
            try:
                return int(result)
            except ValueError:
                pass
        
        try:
            return float(result)
        except ValueError:
            pass
        
        if result.lower() in ('true', 'false'):
            return result.lower() == 'true'
        
        return result
    else:
        return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    from ..utils.logging_config import configure_uvicorn_logging
    
    configure_uvicorn_logging()
    
    async def delayed_configure():
        await asyncio.sleep(0.1)
        configure_uvicorn_logging()
    asyncio.create_task(delayed_configure())
    
    # Initialize on startup
    collector = MockCollector(source="BMS")
    set_app_state(collector=collector)

    # Load configuration
    config_path = Path(__file__).parent.parent.parent / "config" / "app.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
    config = expand_env_vars(config)

    # Merge infrastructure overrides (Redis, InfluxDB, MQTT, PostgreSQL) if present
    overrides_path = Path(__file__).parent.parent.parent / "config" / "infrastructure_overrides.yaml"
    if overrides_path.exists():
        try:
            with open(overrides_path, "r") as f:
                overrides = yaml.safe_load(f) or {}
            overrides = expand_env_vars(overrides)
            _deep_merge(config, overrides)
            logger.info("✓ Loaded infrastructure overrides from config/infrastructure_overrides.yaml")
        except Exception as e:
            logger.warning(f"Failed to load infrastructure overrides: {e}")

    set_app_state(config=config)

    try:
        ConfigValidator.validate_and_warn(config)
    except Exception as e:
        logger.warning(f"Configuration validation failed: {e}")

    # Initialize InfluxDB client
    try:
        db_config = config.get("database", {})
        influx_config = db_config.get("influxdb", {})
        influx_url = influx_config.get("url") or os.getenv("INFLUXDB_URL", "http://localhost:8086")
        influx_token = (influx_config.get("token") or os.getenv("INFLUXDB_TOKEN", "")).strip()
        influx_org = influx_config.get("org") or os.getenv("INFLUXDB_ORG", "bess")
        influx_bucket = influx_config.get("bucket") or os.getenv("INFLUXDB_BUCKET", "alarms")

        if influx_token:
            use_pool = influx_config.get("use_connection_pool", True)
            pool_max_connections = influx_config.get("pool_max_connections", 5)
            
            influx_client = InfluxDBClient(
                url=influx_url,
                token=influx_token,
                org=influx_org,
                bucket=influx_bucket,
                use_connection_pool=use_pool,
                pool_max_connections=pool_max_connections,
            )
            logger.info(f"✓ InfluxDB client connected: {influx_url} (org: {influx_org}, bucket: {influx_bucket})")
            # Ensure default bucket exists (avoids "bucket 'alarms' not found" when querying without site_id)
            try:
                buckets_api = influx_client.client.buckets_api()
                buckets = buckets_api.find_buckets()
                bucket_list = buckets.buckets if hasattr(buckets, "buckets") else (buckets if isinstance(buckets, list) else list(buckets))
                if not any(b.name == influx_bucket for b in bucket_list):
                    from influxdb_client.domain.bucket import Bucket
                    from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
                    orgs_api = influx_client.client.organizations_api()
                    orgs = orgs_api.find_organizations()
                    org_list = orgs.orgs if hasattr(orgs, "orgs") else (orgs if isinstance(orgs, list) else list(orgs))
                    org_id = next((o.id for o in org_list if o.name == influx_org), influx_org)
                    from ..storage.optimization_config import OptimizationConfig
                    retention_seconds = OptimizationConfig.RAW_DATA_RETENTION_DAYS * 86400
                    retention_rules = BucketRetentionRules(type="expire", every_seconds=retention_seconds)
                    buckets_api.create_bucket(bucket=Bucket(name=influx_bucket, org_id=org_id, retention_rules=[retention_rules]))
                    logger.info(f"✓ Created default bucket: {influx_bucket}")
            except Exception as bucket_err:
                logger.warning(f"Could not ensure default bucket {influx_bucket} exists: {bucket_err}")
        else:
            logger.warning(
                "⚠ InfluxDB token not configured (INFLUXDB_TOKEN is empty). "
                "Data will not be written to database."
            )
            influx_client = None
    except ValueError as e:
        logger.error(f"✗ InfluxDB configuration error: {e}")
        influx_client = None
    except Exception as e:
        logger.error(f"✗ InfluxDB connection failed: {e}")
        influx_client = None
    
    set_app_state(influx_client=influx_client)
    
    # Initialize Event Bus
    try:
        from ..core.event_bus import get_event_bus
        event_bus = get_event_bus()
        set_app_state(event_bus=event_bus)
        logger.info("✓ Event bus initialized")
    except Exception as e:
        logger.warning(f"⚠ Failed to initialize event bus: {e}")
        set_app_state(event_bus=None)
    
    # Initialize Query Cache
    try:
        from ..storage.query_cache import QueryCache
        db_config = config.get("database", {})
        redis_config = db_config.get("redis", {})
        
        cache_type = "redis" if redis_config.get("host") else "memory"
        query_cache = QueryCache(
            cache_type=cache_type,
            config={"redis": redis_config},
            default_ttl=config.get("cache", {}).get("query_cache_ttl", 60),
        )
        set_app_state(query_cache=query_cache)
        logger.info(f"✓ Query cache initialized ({cache_type})")
    except Exception as e:
        logger.warning(f"⚠ Failed to initialize query cache: {e}, continuing without cache")
        set_app_state(query_cache=None)

    # Initialize PostgreSQL database
    postgres_metadata_storage = None
    try:
        from ..core.database import get_database
        db_config = config.get("database", {})
        pg_config = db_config.get("postgresql", {})
        
        if pg_config.get("password") or os.getenv("DB_PASSWORD"):
            # Import models to ensure they're registered with Base.metadata before database initialization
            from ..core.database import RuleModel, DiagnosticModel  # noqa: F401
            database = get_database(config=pg_config)
            from ..storage.postgresql_metadata import PostgreSQLMetadataStorage
            postgres_metadata_storage = PostgreSQLMetadataStorage(database)
            set_app_state(postgres_metadata_storage=postgres_metadata_storage)
            logger.info("✓ PostgreSQL metadata storage initialized")
        else:
            logger.info("ℹ PostgreSQL not configured (no password), skipping PostgreSQL storage")
    except Exception as e:
        logger.warning(f"⚠ Failed to initialize PostgreSQL metadata storage: {e}")
        postgres_metadata_storage = None

    # Initialize InfluxDB metadata storage
    influx_metadata_storage = None
    if influx_client:
        try:
            from ..storage.influxdb_metadata import InfluxDBMetadataStorage
            influx_metadata_storage = InfluxDBMetadataStorage(influx_client)
            logger.info("✓ InfluxDB metadata storage initialized")
        except Exception as e:
            logger.warning(f"⚠ Failed to initialize InfluxDB metadata storage: {e}")

    # Initialize Rule Engine
    try:
        rule_engine_config = config.get("rule_engine", {})
        rules_file = rule_engine_config.get("rules_file", "config/rules.yaml")
        site_rules_dir = rule_engine_config.get("site_rules_dir")
        enable_multi_site = rule_engine_config.get("enable_multi_site", False)

        site_manager = SiteManager(
            site_rules_dir=site_rules_dir,
            influx_metadata_storage=influx_metadata_storage,
            postgres_metadata_storage=postgres_metadata_storage,
            container_manager=None
        )
        
        rule_engine = RuleEngine(
            rules_file=rules_file,
            site_rules_dir=site_rules_dir,
            enable_multi_site=enable_multi_site,
            site_manager=site_manager,
        )
        logger.info(f"✓ Rule engine initialized with {len(rule_engine.get_rules())} rules")
        if enable_multi_site:
            logger.info("✓ Multi-site support: enabled")
        
        set_app_state(site_manager=site_manager)
        sites = site_manager.get_all_sites()
        if sites:
            logger.info(f"✓ Site manager initialized with {len(sites)} sites")
        else:
            logger.info("✓ Site manager initialized (no sites configured)")
    except Exception as e:
        logger.warning(f"⚠ Rule engine initialization failed: {e}")
        rule_engine = None

    # Initialize LLM Diagnostic Service
    llm_service = None
    try:
        llm_config = config.get("llm", {})
        provider = llm_config.get("provider")
        if provider and provider != "null" and str(provider).lower() != "none":
            llm_service = LLMDiagnosticService.from_config(llm_config)
            logger.info(f"✓ LLM diagnostic service initialized: {provider}")
        else:
            logger.info("ℹ LLM diagnostic service disabled (no provider configured)")
    except Exception as e:
        logger.warning(f"⚠ LLM diagnostic service initialization failed: {e}")

    # Initialize Grafana client
    grafana_client = None
    annotation_service = None
    try:
        grafana_config = config.get("grafana", {})
        if grafana_config.get("api_key"):
            grafana_client = GrafanaClient.from_config(grafana_config)
            annotation_service = AnnotationService(grafana_client)
            logger.info(f"✓ Grafana client initialized: {grafana_config.get('url')}")
    except Exception as e:
        logger.warning(f"⚠ Grafana client initialization failed: {e}")

    # Initialize Email service
    email_service = None
    try:
        email_config = config.get("email", {})
        smtp_host = email_config.get("smtp_host")
        smtp_user = email_config.get("smtp_user")
        smtp_password = email_config.get("smtp_password")
        
        if smtp_host and smtp_host != "smtp.example.com" and smtp_user and smtp_password:
            email_service = EmailService.from_config(email_config)
            logger.info(f"✓ Email service initialized: {smtp_host}")
        else:
            logger.warning(f"⚠ Email service not configured: smtp_host={smtp_host}, smtp_user={'***' if smtp_user else None}")
    except Exception as e:
        logger.warning(f"⚠ Email service initialization failed: {e}", exc_info=True)
    
    # Store email service in app state
    set_app_state(email_service=email_service)

    # Initialize Device Registry
    device_registry = DeviceRegistry(
        influx_metadata_storage=influx_metadata_storage,
        postgres_metadata_storage=postgres_metadata_storage
    )
    set_app_state(device_registry=device_registry)
    
    # Initialize device integrations
    integrations: Dict[DeviceType, DeviceIntegration] = {}
    
    try:
        from ..core.integration import IntegrationConfig
        from ..integrations.bms.collector import BMSIntegration
        
        bms_config = IntegrationConfig(
            enabled=True,
            device_type=DeviceType.BMS,
            api_url=os.getenv("BMS_API_URL", ""),
            api_key=os.getenv("BMS_API_KEY", ""),
            interval=int(os.getenv("BMS_INTERVAL", "30")),
            timeout=int(os.getenv("BMS_TIMEOUT", "10")),
        )
        bms_integration = BMSIntegration(bms_config)
        integrations[DeviceType.BMS] = bms_integration
        logger.info("✓ BMS integration initialized")
    except Exception as e:
        logger.warning(f"⚠ Integration initialization failed: {e}")
    
    set_app_state(integrations=integrations)

    # Initialize WebSocket Manager
    websocket_manager = WebSocketManager()
    await websocket_manager.start_heartbeat(interval=30)
    set_app_state(websocket_manager=websocket_manager)
    logger.info("✓ WebSocket manager initialized")
    
    # Start periodic device status check task
    async def periodic_device_status_check():
        """Periodically check device status and broadcast stats_updated"""
        while True:
            try:
                await asyncio.sleep(10)
                
                current_app_state = get_app_state()
                current_device_registry = current_app_state.get("device_registry")
                current_websocket_manager = current_app_state.get("websocket_manager")
                
                if current_device_registry and current_websocket_manager:
                    all_devices = current_device_registry.get_all_devices()
                    now = datetime.now(timezone.utc)
                    inactive_timeout_seconds = 30
                    
                    devices_need_update = False
                    devices_changed = []
                    for device in all_devices:
                        if device.status.value == "active" and device.last_seen:
                            try:
                                if isinstance(device.last_seen, str):
                                    if device.last_seen.endswith("Z"):
                                        last_seen_dt = datetime.fromisoformat(device.last_seen.replace("Z", "+00:00"))
                                    else:
                                        last_seen_dt = datetime.fromisoformat(device.last_seen)
                                    if last_seen_dt.tzinfo is None:
                                        last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                                else:
                                    last_seen_dt = device.last_seen
                                    if last_seen_dt.tzinfo is None:
                                        last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                                
                                time_since_last_seen = (now - last_seen_dt).total_seconds()
                                if time_since_last_seen > inactive_timeout_seconds:
                                    previous_status = device.status
                                    device.mark_inactive()
                                    if previous_status != device.status:
                                        devices_changed.append(device.device_id)
                                        devices_need_update = True
                                        if current_device_registry._influx_storage:
                                            try:
                                                device_dict = device.to_dict()
                                                current_device_registry._influx_storage.save_device(device_dict)
                                            except Exception as e:
                                                logger.debug(f"Failed to save inactive status for device {device.device_id}: {e}")
                            except Exception:
                                pass
                    
                    if devices_need_update and devices_changed:
                        await current_websocket_manager.broadcast(
                            EventType.STATS_UPDATED,
                            {
                                "reason": "device_status_changed",
                                "device_ids": devices_changed,
                            },
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error in periodic device status check: {e}")
    
    status_check_task = asyncio.create_task(periodic_device_status_check())
    set_app_state(device_status_check_task=status_check_task)
    logger.info("✓ Periodic device status check task started (every 10 seconds)")

    # Initialize Agent Service
    if rule_engine:
        data_flow_config = config.get("agent", {}).get("data_flow", {})
        device_status_config = data_flow_config.get("device_status_check", {})
        
        agent_service = AgentService(
            rule_engine=rule_engine,
            llm_diagnostic_service=llm_service,
            grafana_client=grafana_client,
            annotation_service=annotation_service,
            influx_client=influx_client,
            email_service=email_service,
            integrations=integrations,
            check_device_status=device_status_config.get("enabled", True),
            auto_register_devices=device_status_config.get("auto_register_devices", True),
            reject_inactive_devices=device_status_config.get("reject_inactive_devices", False),
        )
        auto_diagnostic = config.get("llm", {}).get("auto_diagnostic", False)
        agent_service._auto_diagnostic_enabled = auto_diagnostic
        if auto_diagnostic:
            logger.info("✓ Auto-diagnostic enabled")
        else:
            logger.info("ℹ Auto-diagnostic disabled")
        logger.info("✓ Agent service initialized")
        await agent_service.start()
        set_app_state(agent_service=agent_service)
        
        if agent_service and agent_service.container_manager:
            site_manager.set_container_manager(agent_service.container_manager)
            logger.info("✓ Site manager connected to container manager")
        
        logger.info("ℹ Data collection is now manual via API endpoints")

    # Initialize MQTT Client
    mqtt_client = None
    mqtt_handler = None
    try:
        mqtt_config = config.get("mqtt", {})
        mqtt_broker_url = mqtt_config.get("broker_url") or os.getenv("MQTT_BROKER_URL", "")
        mqtt_client_id = mqtt_config.get("client_id") or os.getenv("MQTT_CLIENT_ID", "")
        mqtt_username = mqtt_config.get("username") or os.getenv("MQTT_USERNAME")
        mqtt_password = mqtt_config.get("password") or os.getenv("MQTT_PASSWORD")

        if mqtt_broker_url:
            mqtt_client = MQTTClient(
                broker_url=mqtt_broker_url,
                client_id=mqtt_client_id,
                username=mqtt_username if mqtt_username else None,
                password=mqtt_password if mqtt_password else None,
            )

            if mqtt_client.connect():
                logger.info(f"✓ MQTT client connected: {mqtt_broker_url}")

                if agent_service:
                    mqtt_handler = MQTTMessageHandler(agent_service)

                    mqtt_client.subscribe(
                        topic="sites/+/data/+",
                        handler=lambda topic, payload: mqtt_handler.handle_device_data(
                            topic, payload
                        ),
                        qos=1,
                    )

                    mqtt_client.subscribe(
                        topic="sites/+/alarms/+",
                        handler=lambda topic, payload: mqtt_handler.handle_alarm(
                            topic, payload
                        ),
                        qos=1,
                    )

                    logger.info("✓ MQTT subscriptions active")
            else:
                logger.warning("⚠ MQTT connection failed")
                mqtt_client = None
        else:
            logger.info("ℹ MQTT not configured")
    except Exception as e:
        logger.warning(f"⚠ MQTT initialization failed: {e}")
        mqtt_client = None
    
    set_app_state(
        mqtt_client=mqtt_client,
        mqtt_handler=mqtt_handler,
        integration_manager=None,
        data_collection_service=None,
    )

    yield

    # Cleanup on shutdown
    app_state = get_app_state()
    mqtt_handler = app_state.get("mqtt_handler")
    mqtt_client = app_state.get("mqtt_client")
    influx_client = app_state.get("influx_client")
    device_status_check_task = app_state.get("device_status_check_task")
    
    if device_status_check_task:
        device_status_check_task.cancel()
        try:
            await device_status_check_task
        except asyncio.CancelledError:
            pass
    
    if mqtt_handler:
        mqtt_handler.shutdown()
    
    if mqtt_client:
        mqtt_client.disconnect()

    agent_service = app_state.get("agent_service")
    if agent_service:
        await agent_service.stop()
        logger.info("✓ Agent service stopped")
    
    if influx_client:
        influx_client.close()
        logger.info("✓ InfluxDB client closed")
    
    set_app_state(
        collector=None,
        influx_client=None,
        agent_service=None,
        mqtt_client=None,
        mqtt_handler=None,
        integration_manager=None,
        data_collection_service=None,
    )

