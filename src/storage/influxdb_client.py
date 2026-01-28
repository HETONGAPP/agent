"""
InfluxDB client
Supports multi-site data storage with site_id tags
Uses connection pool for better performance
"""
import logging

logger = logging.getLogger(__name__)


try:
    from influxdb_client import InfluxDBClient as InfluxClient
    from influxdb_client.client.write_api import ASYNCHRONOUS, SYNCHRONOUS

    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    print("Warning: influxdb-client not installed, InfluxDB functionality unavailable")
    # Create dummy classes for type hints when not available
    InfluxClient = None
    SYNCHRONOUS = None
    ASYNCHRONOUS = None

from typing import Any, Dict, List, Optional  # noqa: E402

from ..models.alarm import Alarm  # noqa: E402
from ..models.device_data import DeviceData  # noqa: E402
from .connection_pool import get_connection_pool  # noqa: E402
from .influxdb_writer import InfluxDBWriter  # noqa: E402
from .influxdb_querier import InfluxDBQuerier  # noqa: E402

# Try to import BMSData from integration module
try:
    from ..integrations.bms import BMSData
except ImportError:
    BMSData = None  # BMSData not available


class InfluxDBClient:
    """InfluxDB client wrapper with multi-site support"""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        use_async: bool = False,
        batch_size: int = 100,
        use_connection_pool: bool = True,
        pool_max_connections: int = 5,
    ):
        """
        Initialize InfluxDB client

        Args:
            url: InfluxDB URL
            token: Access token
            org: Organization name
            bucket: Bucket name
            use_async: Use asynchronous write API for better performance
            batch_size: Batch size for async writes
            use_connection_pool: Use connection pool for connection reuse
            pool_max_connections: Maximum connections in pool (if using pool)
        """
        if not INFLUXDB_AVAILABLE:
            raise ImportError(
                "influxdb-client not installed, please run: pip install influxdb-client"
            )

        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        self.use_async = use_async
        self.batch_size = batch_size
        self.use_connection_pool = use_connection_pool

        # Validate token
        if not token or not token.strip():
            raise ValueError(
                "InfluxDB token is empty. Please set INFLUXDB_TOKEN environment variable. "
                "Run 'python scripts/setup_influxdb.py' to set up InfluxDB."
            )

        # Initialize connection pool if enabled
        if use_connection_pool:
            self._connection_pool = get_connection_pool(max_connections=pool_max_connections)
            # Get client from pool
            self._pool_client = self._connection_pool.get_or_create_client(url, token, org)
            self.client = self._pool_client
        else:
            # Direct client creation (no pool)
            self.client = InfluxClient(url=url, token=token, org=org)
            self._connection_pool = None
            self._pool_client = None

        # Verify connection by checking health
        try:
            health = self.client.health()
            if health.status != "pass":
                logger.warning(f"InfluxDB health check returned: {health.status}")
        except Exception as e:
            logger.warning(f"InfluxDB health check failed: {e}. Connection may still work.")

        # Use async write API for better performance
        if use_async:
            self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        else:
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

        self.query_api = self.client.query_api()
        self._write_buffer = []  # Buffer for batch writes
        
        # Initialize writer and querier for modular operations
        self.writer = InfluxDBWriter(self)
        self.querier = InfluxDBQuerier(self)

    def write_alarm(
        self, alarm: Alarm, flush: bool = False, site_id: Optional[str] = None
    ):
        """Write alarm - delegated to writer"""
        return self.writer.write_alarm(alarm, flush=flush, site_id=site_id)

    def write_bms_data(self, bms_data: BMSData, site_id: Optional[str] = None):
        """Write BMS data - delegated to writer"""
        return self.writer.write_bms_data(bms_data, site_id=site_id)

    def write_device_data(self, device_data: DeviceData, flush: bool = False):
        """Write device data - delegated to writer"""
        return self.writer.write_device_data(device_data, flush=flush)

    def write_diagnostic(
        self, alarm_id: str, diagnostic: Dict[str, Any], site_id: Optional[str] = None, flush: bool = False
    ):
        """Write diagnostic - delegated to writer"""
        return self.writer.write_diagnostic(alarm_id, diagnostic, site_id=site_id, flush=flush)

    def flush(self):
        """Flush all buffered writes"""
        if self.use_async and self._write_buffer:
            logger.debug(
                f"  [InfluxDB] Flushing {len(self._write_buffer)} buffered points to InfluxDB"
            )
            try:
                self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                logger.debug(
                    f"  ✓ [InfluxDB] Successfully flushed {len(self._write_buffer)} points to bucket '{self.bucket}'"
                )
                self._write_buffer = []
            except Exception as e:
                logger.error(
                    f"  ✗ [InfluxDB] Failed to flush points: {e}", exc_info=True
                )
                raise
        elif not self.use_async:
            logger.debug("  [InfluxDB] Sync mode - no buffer to flush")

    def query_alarms(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        alarm_type: Optional[str] = None,
        severity: Optional[str] = None,
        source: Optional[str] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query alarms - delegated to querier"""
        return self.querier.query_alarms(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            severity=severity,
            source=source,
            site_id=site_id,
            device_type=device_type,
            limit=limit,
        )

    def query_diagnostics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query diagnostics - delegated to querier"""
        return self.querier.query_diagnostics(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            risk_level=risk_level,
            site_id=site_id,
            device_type=device_type,
            limit=limit,
        )

    def query_time_series_metrics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "1h",  # "1h", "1d", etc.
        metric_type: str = "alarms",  # "alarms", "diagnostics", "devices"
        group_by: Optional[str] = None,  # "severity", "risk_level", "status", etc.
        site_id: Optional[str] = None,  # Site ID for container mode
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query time series metrics - delegated to querier"""
        return self.querier.query_time_series_metrics(
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            metric_type=metric_type,
            group_by=group_by,
            site_id=site_id,
            limit=limit,
        )

    def query_device_time_series(
        self,
        device_ids: Optional[List[str]] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        metric: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "1m",  # "1m", "5m", "1h", "1d", etc.
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query device time series - delegated to querier"""
        return self.querier.query_device_time_series(
            device_ids=device_ids,
            site_id=site_id,
            device_type=device_type,
            metric=metric,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            limit=limit,
        )

    def delete_device_data(self, device_id: str) -> int:
        """
        Delete all historical data for a device from InfluxDB
        
        This deletes data from:
        - device_data measurement
        - alarms measurement (if device_id matches)
        - diagnostics measurement (if device_id matches)
        
        Args:
            device_id: Device ID to delete data for
            
        Returns:
            Number of data points deleted (approximate)
        """
        if not INFLUXDB_AVAILABLE:
            logger.warning("[InfluxDB] Cannot delete device data: InfluxDB client not available")
            return 0
        
        try:
            from datetime import datetime, timedelta, UTC
            
            delete_api = self.client.delete_api()
            
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            deleted_count = 0
            
            # Delete device_data measurement
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=f'_measurement="device_data" AND device_id="{device_id}"',
                    bucket=self.bucket,
                    org=self.org
                )
                logger.info(f"[InfluxDB] Deleted device_data for device {device_id}")
                deleted_count += 1  # Approximate count
            except Exception as e:
                logger.warning(f"[InfluxDB] Failed to delete device_data for {device_id}: {e}")
            
            # Delete alarms related to this device
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=f'_measurement="alarms" AND device_id="{device_id}"',
                    bucket=self.bucket,
                    org=self.org
                )
                logger.info(f"[InfluxDB] Deleted alarms for device {device_id}")
                deleted_count += 1
            except Exception as e:
                logger.warning(f"[InfluxDB] Failed to delete alarms for {device_id}: {e}")
            
            # Delete diagnostics related to this device
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=f'_measurement="diagnostics" AND device_id="{device_id}"',
                    bucket=self.bucket,
                    org=self.org
                )
                logger.info(f"[InfluxDB] Deleted diagnostics for device {device_id}")
                deleted_count += 1
            except Exception as e:
                logger.warning(f"[InfluxDB] Failed to delete diagnostics for {device_id}: {e}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"[InfluxDB] Error deleting device data for {device_id}: {e}", exc_info=True)
            return 0
    
    def delete_diagnostic(self, alarm_id: str, site_id: Optional[str] = None) -> bool:
        """
        Delete diagnostic report from InfluxDB
        
        Args:
            alarm_id: Alarm ID associated with the diagnostic
            site_id: Optional site ID for filtering
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not INFLUXDB_AVAILABLE:
            logger.warning("[InfluxDB] Cannot delete diagnostic: InfluxDB client not available")
            return False
        
        try:
            from datetime import datetime, timedelta, UTC
            
            delete_api = self.client.delete_api()
            
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            # Build predicate
            predicate = f'_measurement="diagnostics" AND alarm_id="{alarm_id}"'
            if site_id:
                predicate += f' AND site_id="{site_id}"'
            
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=predicate,
                    bucket=self.bucket,
                    org=self.org
                )
                logger.info(f"[InfluxDB] Deleted diagnostic for alarm {alarm_id}" + (f" (site_id={site_id})" if site_id else ""))
                return True
            except Exception as e:
                logger.warning(f"[InfluxDB] Failed to delete diagnostic for alarm {alarm_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete diagnostic: {e}", exc_info=True)
            return False
    
    def delete_all_alarms(self) -> bool:
        """
        Delete all alarms from InfluxDB
        
        Returns:
            True if successful, False otherwise
        """
        if not INFLUXDB_AVAILABLE:
            logger.warning("[InfluxDB] Cannot delete alarms: InfluxDB client not available")
            return False
        
        try:
            from datetime import datetime, timedelta, UTC
            
            delete_api = self.client.delete_api()
            
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            delete_api.delete(
                start=start_time,
                stop=stop_time,
                predicate='_measurement="alarms"',
                bucket=self.bucket,
                org=self.org
            )
            logger.info("[InfluxDB] Deleted all alarms")
            return True
        except Exception as e:
            logger.error(f"[InfluxDB] Error deleting all alarms: {e}", exc_info=True)
            return False
    
    def delete_all_diagnostics(self) -> bool:
        """
        Delete all diagnostic reports from InfluxDB
        
        Returns:
            True if successful, False otherwise
        """
        if not INFLUXDB_AVAILABLE:
            logger.warning("[InfluxDB] Cannot delete diagnostics: InfluxDB client not available")
            return False
        
        try:
            from datetime import datetime, timedelta, UTC
            
            delete_api = self.client.delete_api()
            
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            delete_api.delete(
                start=start_time,
                stop=stop_time,
                predicate='_measurement="diagnostics"',
                bucket=self.bucket,
                org=self.org
            )
            logger.info("[InfluxDB] Deleted all diagnostics")
            return True
        except Exception as e:
            logger.error(f"[InfluxDB] Error deleting all diagnostics: {e}", exc_info=True)
            return False

    def close(self):
        """Close InfluxDB client"""
        self.flush()
        if hasattr(self, "write_api"):
            self.write_api.close()
        
        # Return client to pool if using connection pool
        if self.use_connection_pool and self._connection_pool and self._pool_client:
            try:
                self._connection_pool.return_client(self._pool_client, self.url, self.token, self.org)
                logger.debug("[InfluxDB] Returned client to connection pool")
            except Exception as e:
                logger.warning(f"[InfluxDB] Failed to return client to pool: {e}")
                # Fallback: close directly
                try:
                    self.client.close()
                except Exception:
                    pass
        elif hasattr(self, "client"):
            # Direct close if not using pool
            self.client.close()
