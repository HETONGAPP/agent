"""
Metrics API routes
"""

import logging
from typing import Optional
from fastapi import Depends
from fastapi.responses import JSONResponse
import psutil

from ...storage.influxdb_client import InfluxDBClient
from ...agent.service import AgentService
from ...agent.dependencies import (
    get_influx_client,
    get_agent_service,
)
from ...agent.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)


def register_metrics_routes(app):
    """Register metrics routes"""
    
    @app.get("/api/v1/metrics/timeseries")
    async def get_time_series_metrics(
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "1h",
        metric_type: str = "alarms",
        group_by: Optional[str] = None,
        site_id: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get time series metrics aggregated by time interval"""
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            time_series = influx_client.query_time_series_metrics(
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                metric_type=metric_type,
                group_by=group_by,
            )
            
            return {
                "status": "success",
                "data": {
                    "time_series": time_series,
                    "total": len(time_series),
                    "interval": interval,
                    "metric_type": metric_type,
                },
            }
        except Exception as e:
            logger.error(f"Error getting time series metrics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/metrics/device-timeseries")
    async def get_device_time_series(
        device_ids: Optional[str] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        metric: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "5m",
        since: Optional[str] = None,
        influx_client: Optional[InfluxDBClient] = Depends(get_influx_client),
        agent_service: Optional[AgentService] = Depends(get_agent_service),
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """
        Get device time series data from MQTT/device_data
        
        Args:
            since: ISO format timestamp for incremental queries.
                  If provided, only returns data after this timestamp, ignoring start_time.
        """
        if not influx_client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": "InfluxDB client not initialized",
                },
            )
        
        try:
            device_ids_list = None
            if device_ids:
                device_ids_list = [d.strip() for d in device_ids.split(",") if d.strip()]
            
            query_start_time = start_time
            if since:
                try:
                    from datetime import datetime, UTC
                    since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    now = datetime.now(UTC)
                    diff = now - since_dt
                    if diff.total_seconds() > 0:
                        if diff.total_seconds() < 60:
                            query_start_time = f"-{int(diff.total_seconds())}s"
                        elif diff.total_seconds() < 3600:
                            query_start_time = f"-{int(diff.total_seconds() / 60)}m"
                        elif diff.total_seconds() < 86400:
                            query_start_time = f"-{int(diff.total_seconds() / 3600)}h"
                        else:
                            query_start_time = f"-{int(diff.total_seconds() / 86400)}d"
                    else:
                        query_start_time = "-5m"
                except (ValueError, AttributeError):
                    query_start_time = since
            
            if agent_service and agent_service.container_manager and site_id:
                container = agent_service.container_manager.get_container(site_id, auto_create=False)
                if container:
                    time_series = container.query_device_time_series(
                        device_ids=device_ids_list,
                        device_type=device_type,
                        metric=metric,
                        start_time=query_start_time,
                        end_time=end_time,
                        interval=interval,
                    )
                else:
                    time_series = []
            else:
                time_series = influx_client.query_device_time_series(
                    device_ids=device_ids_list,
                    site_id=site_id,
                    device_type=device_type,
                    metric=metric,
                    start_time=query_start_time,
                    end_time=end_time,
                    interval=interval,
                )
            
            return {
                "status": "success",
                "data": {
                    "time_series": time_series,
                    "total": len(time_series),
                    "interval": interval,
                },
            }
        except Exception as e:
            logger.error(f"Error getting device time series: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )
    
    @app.get("/api/v1/metrics/system")
    async def get_system_metrics(
        _rate_limited: bool = Depends(rate_limit_dependency),
    ):
        """Get system resource metrics (CPU, memory, data throughput)"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory usage
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Network I/O (data throughput)
            network_io = psutil.net_io_counters()
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            
            return {
                "status": "success",
                "data": {
                    "cpu": {
                        "usage_percent": cpu_percent,
                        "count": cpu_count,
                        "frequency_mhz": cpu_freq.current if cpu_freq else None,
                    },
                    "memory": {
                        "total_gb": round(memory.total / (1024 ** 3), 2),
                        "used_gb": round(memory.used / (1024 ** 3), 2),
                        "available_gb": round(memory.available / (1024 ** 3), 2),
                        "usage_percent": memory.percent,
                    },
                    "swap": {
                        "total_gb": round(swap.total / (1024 ** 3), 2),
                        "used_gb": round(swap.used / (1024 ** 3), 2),
                        "usage_percent": swap.percent,
                    },
                    "network": {
                        "bytes_sent_mb": round(network_io.bytes_sent / (1024 ** 2), 2) if network_io else 0,
                        "bytes_recv_mb": round(network_io.bytes_recv / (1024 ** 2), 2) if network_io else 0,
                        "packets_sent": network_io.packets_sent if network_io else 0,
                        "packets_recv": network_io.packets_recv if network_io else 0,
                    },
                    "disk_io": {
                        "read_mb": round(disk_io.read_bytes / (1024 ** 2), 2) if disk_io else 0,
                        "write_mb": round(disk_io.write_bytes / (1024 ** 2), 2) if disk_io else 0,
                        "read_count": disk_io.read_count if disk_io else 0,
                        "write_count": disk_io.write_count if disk_io else 0,
                    },
                },
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)},
            )

