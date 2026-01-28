"""
Site container - Device data operations mixin
Provides device data write, query, and delete for site-specific data
"""
import logging
from typing import Any, Dict, List, Optional

from ..models.device_data import DeviceData

logger = logging.getLogger(__name__)


class SiteDeviceMixin:
    """
    Mixin providing device data operations for SiteContainer.
    Requires: self.site_id, self.bucket, self.influx_client, self.influx_client_base
    """

    def write_device_data(self, device_data: DeviceData, flush: bool = False):
        """Write device data to site container."""
        return self.influx_client.write_device_data(device_data, flush=flush)

    def query_device_time_series(
        self,
        device_ids: Optional[List[str]] = None,
        device_type: Optional[str] = None,
        metric: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "1m",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query device time series from site container."""
        return self.influx_client.query_device_time_series(
            device_ids=device_ids,
            device_type=device_type,
            metric=metric,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            limit=limit,
        )

    def delete_device_data(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
    ) -> int:
        """Delete device data from site container."""
        try:
            from datetime import datetime, timedelta, UTC

            delete_api = self.influx_client_base.client.delete_api()
            predicate = '_measurement="device_data"'
            if device_ids:
                predicate += " AND (" + " OR ".join(f'device_id="{d}"' for d in device_ids) + ")"
            start = start_time if start_time else datetime.now(UTC) - timedelta(days=30)
            stop = end_time if end_time else datetime.now(UTC) + timedelta(days=1)
            delete_api.delete(start=start, stop=stop, predicate=predicate, bucket=self.bucket, org=self.influx_client_base.org)
            logger.info(f"Deleted device data from site {self.site_id}")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete device data from site {self.site_id}: {e}", exc_info=True)
            return 0
