"""
Data Collector Agent
Collects data from the system (alarms, devices, historical)
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import BaseDiagnosticAgent
from ...llm_diagnostic.client import LLMClient

logger = logging.getLogger(__name__)


class DataCollectorAgent(BaseDiagnosticAgent):
    """Agent for collecting diagnostic data"""

    SYSTEM_PROMPT = """You are a data collection expert for BESS diagnostic systems.

Your role is to collect the requested data from the system. You should:
1. Understand what data is requested from the task description
2. Collect the data efficiently
3. Return structured data that can be used by analysis agents

You don't need to analyze the data, just collect it accurately.
"""

    def __init__(
        self,
        llm_client: LLMClient,
        influx_client=None,
        device_registry=None,
    ):
        """
        Initialize data collector agent

        Args:
            llm_client: LLM client
            influx_client: InfluxDB client (optional)
            device_registry: Device registry (optional)
        """
        super().__init__(self.SYSTEM_PROMPT, llm_client, "DataCollectorAgent")
        self.influx_client = influx_client
        self.device_registry = device_registry

    async def analyze(
        self,
        context: Dict[str, Any],
        dependencies: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Collect data based on task description"""
        site_id = context.get("site_id")
        time_range = context.get("time_range", "-24h")
        task_description = context.get("task_description", "").lower()

        try:
            # Determine what data to collect based on task description
            if "alarm" in task_description:
                data = await self._collect_alarms(site_id, time_range)
                data_type = "alarms"
            elif "device" in task_description:
                data = await self._collect_devices(site_id)
                data_type = "devices"
            elif "historical" in task_description or "trend" in task_description:
                data = await self._collect_historical(site_id, time_range, task_description)
                data_type = "historical"
            else:
                # Try to collect all types
                alarms = await self._collect_alarms(site_id, time_range)
                devices = await self._collect_devices(site_id)
                historical = await self._collect_historical(site_id, time_range, task_description)
                data = {
                    "alarms": alarms,
                    "devices": devices,
                    "historical": historical,
                }
                data_type = "all"

            return {
                "status": "success",
                "agent": self.agent_name,
                "data_type": data_type,
                "data": data,
                "summary": self._create_summary(data_type, data),
                "site_id": site_id,
            }

        except Exception as e:
            logger.error(f"Data collection failed: {e}", exc_info=True)
            return {
                "status": "error",
                "agent": self.agent_name,
                "error": str(e),
                "site_id": site_id,
            }

    async def _collect_alarms(self, site_id: str, time_range: str) -> List[Dict[str, Any]]:
        """Collect alarms for site"""
        if not self.influx_client:
            logger.warning("InfluxDB client not available, returning empty alarms")
            return []

        try:
            alarms = self.influx_client.query_alarms(
                site_id=site_id,
                start_time=time_range,
                limit=1000,
            )
            # query_alarms returns List[Dict], not Alarm objects
            logger.info(f"Collected {len(alarms)} alarms for site {site_id}")
            return alarms
        except Exception as e:
            logger.error(f"Failed to collect alarms: {e}", exc_info=True)
            return []

    async def _collect_devices(self, site_id: str) -> List[Dict[str, Any]]:
        """Collect device status for site"""
        devices = []

        # Try to get from device registry
        if self.device_registry:
            try:
                # Get all devices and filter by site_id
                all_devices = self.device_registry.get_all_devices()
                for device in all_devices:
                    # Check if device belongs to this site
                    device_dict = device.to_dict()
                    device_metadata = device_dict.get("metadata", {})
                    device_site_id = device_metadata.get("site_id")
                    
                    if device_site_id == site_id:
                        devices.append({
                            "device_id": device.device_id,
                            "device_type": device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
                            "status": getattr(device, 'status', 'unknown'),
                            "last_seen": getattr(device, 'last_seen', None),
                        })
            except Exception as e:
                logger.warning(f"Failed to get devices from registry: {e}")

        logger.info(f"Collected {len(devices)} devices for site {site_id}")
        return devices

    async def _collect_historical(
        self, site_id: str, time_range: str, task_description: str
    ) -> List[Dict[str, Any]]:
        """Collect historical time-series data"""
        if not self.influx_client:
            logger.warning("InfluxDB client not available, returning empty historical data")
            return []

        # Extract metrics from task description
        metrics = self._extract_metrics_from_description(task_description)
        if not metrics:
            # Default metrics
            metrics = ["soc", "soh", "temperature", "voltage", "current", "power"]

        historical_data = []
        try:
            # Get device IDs for the site
            devices = await self._collect_devices(site_id)
            device_ids = [d.get("device_id") for d in devices if d.get("device_id")][:10]  # Limit to 10 devices

            if not device_ids:
                logger.warning(f"No devices found for site {site_id}")
                return []

            # Query each metric
            for metric in metrics:
                try:
                    time_series = self.influx_client.query_device_time_series(
                        device_ids=device_ids,
                        site_id=site_id,
                        metric=metric,
                        start_time=time_range,
                        interval="1h",
                        limit=100,
                    )
                    historical_data.extend(time_series)
                except Exception as e:
                    logger.warning(f"Failed to query metric {metric}: {e}")

            logger.info(f"Collected {len(historical_data)} historical data points for site {site_id}")
            return historical_data

        except Exception as e:
            logger.error(f"Failed to collect historical data: {e}", exc_info=True)
            return []

    def _extract_metrics_from_description(self, description: str) -> List[str]:
        """Extract metric names from task description"""
        description_lower = description.lower()
        metrics = []

        # Common metrics
        metric_keywords = {
            "soc": "soc",
            "soh": "soh",
            "temperature": "temperature",
            "temp": "temperature",
            "voltage": "voltage",
            "current": "current",
            "power": "power",
            "energy": "energy",
        }

        for keyword, metric in metric_keywords.items():
            if keyword in description_lower and metric not in metrics:
                metrics.append(metric)

        return metrics

    def _create_summary(self, data_type: str, data: Any) -> str:
        """Create summary of collected data"""
        if data_type == "alarms":
            count = len(data) if isinstance(data, list) else 0
            return f"Collected {count} alarms"
        elif data_type == "devices":
            count = len(data) if isinstance(data, list) else 0
            return f"Collected {count} devices"
        elif data_type == "historical":
            count = len(data) if isinstance(data, list) else 0
            return f"Collected {count} historical data points"
        elif data_type == "all":
            alarms_count = len(data.get("alarms", []))
            devices_count = len(data.get("devices", []))
            historical_count = len(data.get("historical", []))
            return f"Collected {alarms_count} alarms, {devices_count} devices, {historical_count} historical points"
        else:
            return "Data collected"

    async def process(self, prompt: str) -> str:
        """Process prompt (required by base class)"""
        # This method is not used directly, analyze() is used instead
        return "Data collection completed"

