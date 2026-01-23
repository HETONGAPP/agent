"""
Integration Service HTTP Client
Core uses this to communicate with integration services (independent apps)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ..models.alarm import Alarm
from ..models.device_data import DeviceData, DeviceType

logger = logging.getLogger(__name__)


@dataclass
class IntegrationServiceInfo:
    """Information about an integration service"""

    service_id: str  # Unique service identifier (e.g., "bms-service-1")
    device_type: DeviceType
    service_url: str  # Base URL of the service (e.g., "http://localhost:8001")
    service_name: str  # Integration name (e.g., "bms")
    version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    last_seen: Optional[datetime] = None
    is_healthy: bool = False


class IntegrationServiceClient:
    """
    HTTP client for communicating with integration services
    Each integration runs as an independent service/app
    """

    def __init__(self, service_info: IntegrationServiceInfo, timeout: int = 10):
        """
        Initialize integration service client

        Args:
            service_info: Service information
            timeout: Request timeout in seconds
        """
        self.service_info = service_info
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            # Create new connector for each session
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
            )
        return self._session

    async def close(self):
        """Close HTTP session and connector"""
        if self._session:
            try:
                if not self._session.closed:
                    # Close session (this will also close the connector)
                    await self._session.close()
                # Wait a bit for cleanup to ensure all connections are closed
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.debug(f"Error closing session: {e}")
            finally:
                self._session = None

    async def health_check(self) -> bool:
        """
        Check if integration service is healthy

        Returns:
            True if service is healthy, False otherwise
        """
        was_healthy = self.service_info.is_healthy

        try:
            session = await self._get_session()
            async with session.get(
                f"{self.service_info.service_url}/health",
                timeout=aiohttp.ClientTimeout(total=2),  # Reduced timeout for faster failure detection
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.service_info.is_healthy = data.get("status") == "healthy"
                    self.service_info.last_seen = datetime.now(UTC)
                    return self.service_info.is_healthy
                self.service_info.is_healthy = False
                return False
        except aiohttp.ClientConnectorError as e:
            self.service_info.is_healthy = False
            # Log at DEBUG level to reduce noise during normal operation
            # Connection failures are expected when services are not running
            logger.debug(
                f"⚠ Connection failed to integration service {self.service_info.service_id} "
                f"({self.service_info.device_type.value}): {e} "
                f"Service URL: {self.service_info.service_url}"
            )
            return False
        except Exception as e:
            self.service_info.is_healthy = False
            # Log at DEBUG level for normal retry scenarios
            logger.debug(
                f"⚠ Health check failed for integration service {self.service_info.service_id} "
                f"({self.service_info.device_type.value}): {e} "
                f"Service URL: {self.service_info.service_url}"
            )
            return False

    async def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover devices from integration service

        Returns:
            List of device information dictionaries
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.service_info.service_url}/api/v1/devices"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    devices = data.get("devices", [])
                    logger.debug(
                        f"Discovered {len(devices)} devices from {self.service_info.service_id}"
                    )
                    return devices
                else:
                    logger.debug(
                        f"⚠ Failed to discover devices from {self.service_info.service_id} "
                        f"({self.service_info.device_type.value}): HTTP {response.status}"
                    )
                    return []
        except aiohttp.ClientConnectorError as e:
            logger.debug(
                f"⚠ Connection failed when discovering devices from "
                f"{self.service_info.service_id} ({self.service_info.device_type.value}): {e} "
                f"Service URL: {self.service_info.service_url}"
            )
            return []
        except Exception as e:
            logger.error(
                f"Error discovering devices from {self.service_info.service_id}: {e}",
                exc_info=True,
            )
            return []

    async def get_device_data(self, device_id: str) -> Optional[DeviceData]:
        """
        Get device data from integration service

        Args:
            device_id: Device ID

        Returns:
            DeviceData object or None if error
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.service_info.service_url}/api/v1/devices/{device_id}/data"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert response to DeviceData
                    return DeviceData.from_dict(data)
                else:
                    logger.debug(
                        f"⚠ Failed to get device data for {device_id} from "
                        f"{self.service_info.service_id} ({self.service_info.device_type.value}): "
                        f"HTTP {response.status}"
                    )
                    return None
        except aiohttp.ClientConnectorError as e:
            logger.debug(
                f"⚠ Connection failed when getting device data for {device_id} from "
                f"{self.service_info.service_id} ({self.service_info.device_type.value}): {e} "
                f"Service URL: {self.service_info.service_url}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Error getting device data for {device_id} from "
                f"{self.service_info.service_id}: {e}",
                exc_info=True,
            )
            return None

    async def collect_alarms(self) -> List[Alarm]:
        """
        Collect alarms from integration service

        Returns:
            List of Alarm objects
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.service_info.service_url}/api/v1/alarms"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    alarms_data = data.get("alarms", [])
                    return [Alarm.from_dict(alarm_data) for alarm_data in alarms_data]
                else:
                    logger.debug(
                        f"Failed to collect alarms from {self.service_info.service_id}: "
                        f"HTTP {response.status}"
                    )
                    return []
        except Exception as e:
            logger.error(
                f"Error collecting alarms from {self.service_info.service_id}: {e}",
                exc_info=True,
            )
            return []

    async def get_context_data(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """
        Get alarm context data from integration service

        Args:
            alarm_id: Alarm ID

        Returns:
            Context data dictionary or None if error
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.service_info.service_url}/api/v1/alarms/{alarm_id}/context"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("context", {})
                else:
                    logger.debug(
                        f"Failed to get context for alarm {alarm_id} from "
                        f"{self.service_info.service_id}: HTTP {response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(
                f"Error getting context for alarm {alarm_id} from "
                f"{self.service_info.service_id}: {e}",
                exc_info=True,
            )
            return None
