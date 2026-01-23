"""
MQTT Message Handler
Handles incoming MQTT messages and processes device data
Optimized with batch processing for better performance
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime, UTC
from concurrent.futures import ThreadPoolExecutor
from collections import deque

from ..models.device_data import DeviceData, DeviceType

if TYPE_CHECKING:
    from ..agent.service import AgentService

logger = logging.getLogger(__name__)


class MQTTMessageHandler:
    """
    Handles MQTT messages from sites
    Parses messages and processes through AgentService
    Uses batch processing to improve throughput
    Uses thread pool executor to safely handle async calls from sync context
    """

    def __init__(self, agent_service: "AgentService"):
        """
        Initialize MQTT message handler

        Args:
            agent_service: AgentService instance for processing
        """
        self.agent_service = agent_service
        # Use thread pool executor to safely run async code from sync context
        # Increased workers for better throughput
        self._executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="mqtt_handler")

    def handle_device_data(self, topic: str, payload: Dict[str, Any]):
        """
        Handle device data message from MQTT
        Safely handles async processing from sync MQTT callback

        Args:
            topic: MQTT topic (e.g., sites/SITE_001/data/bms)
            payload: Message payload
        """
        device_id = payload.get("device_id", "N/A")
        source = payload.get("source", "N/A")
        logger.debug(
            f"📨 [Handler] Processing device data - topic: {topic}, "
            f"device_id: {device_id}, source: {source}"
        )
        try:
            # Parse topic to extract site_id and device_type
            # Format: sites/{site_id}/data/{device_type}
            parts = topic.split("/")
            if len(parts) >= 4 and parts[0] == "sites" and parts[2] == "data":
                site_id = parts[1]
                device_type_str = parts[3]
                logger.debug(
                    f"  [Handler] Parsed - site_id: {site_id}, device_type: {device_type_str}"
                )

                # Create DeviceData from payload
                device_data = self._parse_device_data(payload, site_id, device_type_str)
                logger.debug(
                    f"  [Handler] Created DeviceData - device_id: {device_data.device_id}, "
                    f"data fields: {list(device_data.data.keys())}"
                )

                # Process through agent service (async call) - use executor to avoid blocking
                future = self._executor.submit(self._process_device_data_async, device_data)
                # Don't wait for result to avoid blocking MQTT callback
                # Result will be logged asynchronously
                future.add_done_callback(
                    lambda f: self._log_device_data_result(topic, f)
                )
            else:
                logger.warning(f"⚠ [Handler] Invalid topic format: {topic}")

        except Exception as e:
            logger.error(
                f"✗ [Handler] Error handling device data from {topic}: {e}",
                exc_info=True,
            )

    def handle_alarm(self, topic: str, payload: Dict[str, Any]):
        """
        Handle alarm message from MQTT
        Safely handles async processing from sync MQTT callback

        Args:
            topic: MQTT topic (e.g., sites/SITE_001/alarms/over_temperature)
            payload: Message payload
        """
        try:
            # Parse topic to extract site_id and alarm_type
            # Format: sites/{site_id}/alarms/{alarm_type}
            parts = topic.split("/")
            if len(parts) >= 4 and parts[0] == "sites" and parts[2] == "alarms":
                site_id = parts[1]
                alarm_type = parts[3]

                # Create DeviceData from alarm payload
                device_data = self._parse_alarm_data(payload, site_id, alarm_type)

                # Process through agent service (async call) - use executor to avoid blocking
                future = self._executor.submit(self._process_device_data_async, device_data)
                # Don't wait for result to avoid blocking MQTT callback
                future.add_done_callback(
                    lambda f: self._log_alarm_result(topic, f)
                )
            else:
                logger.warning(f"Invalid topic format: {topic}")

        except Exception as e:
            logger.error(f"Error handling alarm from {topic}: {e}", exc_info=True)

    def _process_device_data_async(self, device_data: DeviceData) -> Dict[str, Any]:
        """
        Process device data asynchronously in a new event loop
        This method runs in a thread pool executor

        Args:
            device_data: DeviceData to process

        Returns:
            Processing result
        """
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.agent_service.process_device_data(device_data)
            )
        finally:
            loop.close()

    def _log_device_data_result(self, topic: str, future):
        """Log the result of device data processing"""
        try:
            result = future.result()
            logger.info(f"Processed device data from {topic}: {result.get('alarms_processed', 0)} alarms")
        except Exception as e:
            logger.error(f"Error processing device data from {topic}: {e}", exc_info=True)

    def _log_alarm_result(self, topic: str, future):
        """Log the result of alarm processing"""
        try:
            result = future.result()
            logger.info(f"Processed alarm from {topic}: {result.get('alarms_processed', 0)} alarms")
        except Exception as e:
            logger.error(f"Error processing alarm from {topic}: {e}", exc_info=True)

    def shutdown(self):
        """Shutdown the executor"""
        self._executor.shutdown(wait=True)

    def _parse_device_data(
        self, payload: Dict[str, Any], site_id: str, device_type_str: str
    ) -> DeviceData:
        """
        Parse device data from MQTT payload

        Args:
            payload: Message payload
            site_id: Site ID
            device_type_str: Device type string

        Returns:
            DeviceData object
        """
        try:
            device_type = DeviceType(device_type_str.upper())
        except ValueError:
            device_type = DeviceType.OTHER

        # Parse timestamp with error handling
        timestamp_str = payload.get("timestamp")
        if timestamp_str:
            if isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    # Ensure timezone-aware
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}, using current time")
                    timestamp = datetime.now(UTC)
            elif isinstance(timestamp_str, (int, float)):
                # Unix timestamp
                try:
                    if timestamp_str > 1e10:  # Milliseconds
                        timestamp_str = timestamp_str / 1000
                    timestamp = datetime.fromtimestamp(timestamp_str, tz=UTC)
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}, using current time")
                    timestamp = datetime.now(UTC)
            elif isinstance(timestamp_str, datetime):
                timestamp = timestamp_str
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
            else:
                logger.warning(f"Invalid timestamp type: {type(timestamp_str)}, using current time")
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)
            logger.debug(
                f"  [Handler] No timestamp in payload, using current time: {timestamp}"
            )

        return DeviceData(
            device_id=payload.get("device_id", "unknown"),
            device_type=device_type,
            timestamp=timestamp,
            source=payload.get("source", "MQTT"),
            site_id=site_id,
            site_name=payload.get("site_name"),
            data=payload.get("data", {}),
            metadata=payload.get("metadata", {}),
        )

    def _parse_alarm_data(
        self, payload: Dict[str, Any], site_id: str, alarm_type: str
    ) -> DeviceData:
        """
        Parse alarm data from MQTT payload

        Args:
            payload: Message payload
            site_id: Site ID
            alarm_type: Alarm type

        Returns:
            DeviceData object
        """
        # Extract device information from alarm
        device_id = payload.get("device_id", "unknown")
        device_type_str = payload.get("device_type", "OTHER")

        try:
            device_type = DeviceType(device_type_str.upper())
        except ValueError:
            device_type = DeviceType.OTHER

        # Parse timestamp with error handling
        timestamp_str = payload.get("timestamp")
        if timestamp_str:
            if isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    # Ensure timezone-aware
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}, using current time")
                    timestamp = datetime.now(UTC)
            elif isinstance(timestamp_str, (int, float)):
                # Unix timestamp
                try:
                    if timestamp_str > 1e10:  # Milliseconds
                        timestamp_str = timestamp_str / 1000
                    timestamp = datetime.fromtimestamp(timestamp_str, tz=UTC)
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}, using current time")
                    timestamp = datetime.now(UTC)
            elif isinstance(timestamp_str, datetime):
                timestamp = timestamp_str
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
            else:
                logger.warning(f"Invalid timestamp type: {type(timestamp_str)}, using current time")
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)

        # Create data dict from alarm payload
        data = payload.get("data", {})
        if "value" in payload:
            data["value"] = payload["value"]

        return DeviceData(
            device_id=device_id,
            device_type=device_type,
            timestamp=timestamp,
            source=payload.get("source", "MQTT"),
            site_id=site_id,
            site_name=payload.get("site_name"),
            data=data,
            metadata={
                "alarm_type": alarm_type,
                "severity": payload.get("severity"),
                **payload.get("metadata", {}),
            },
        )
