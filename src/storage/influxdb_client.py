"""
InfluxDB client
Supports multi-site data storage with site_id tags
Uses connection pool for better performance
"""
import logging

logger = logging.getLogger(__name__)


try:
    from influxdb_client import InfluxDBClient as InfluxClient
    from influxdb_client import Point
    from influxdb_client.client.write_api import ASYNCHRONOUS, SYNCHRONOUS

    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    print("Warning: influxdb-client not installed, InfluxDB functionality unavailable")
    # Create dummy classes for type hints when not available
    InfluxClient = None
    Point = type("Point", (), {})  # Dummy class for type hints
    SYNCHRONOUS = None
    ASYNCHRONOUS = None

from typing import Any, Dict, List, Optional  # noqa: E402

from ..models.alarm import Alarm  # noqa: E402
from ..models.device_data import DeviceData  # noqa: E402
from .connection_pool import get_connection_pool  # noqa: E402

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

    def _add_site_tag(
        self,
        point,
        site_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add site_id tag to point if available

        Args:
            point: InfluxDB Point object
            site_id: Site ID (direct)
            metadata: Metadata dictionary (may contain site_id)

        Returns:
            Point with site_id tag if available
        """
        if site_id:
            return point.tag("site_id", site_id)

        if metadata and metadata.get("site_id"):
            return point.tag("site_id", metadata["site_id"])

        return point

    def write_alarm(
        self, alarm: Alarm, flush: bool = False, site_id: Optional[str] = None
    ):
        """
        Write alarm data with multi-site support

        Args:
            alarm: Alarm object
            flush: If True, immediately flush buffer (default: False, batch write)
            site_id: Optional site ID for multi-site support
        """
        point = (
            Point("alarms")
            .tag("alarm_id", alarm.alarm_id)
            .tag("alarm_type", alarm.alarm_type)
            .tag("severity", alarm.severity.value)
            .tag("source", alarm.source)
        )

        # Add device_id tag from alarm metadata if available
        device_id = alarm.metadata.get("device_id")
        if device_id:
            point = point.tag("device_id", device_id)

        # Add device_type tag from alarm metadata if available
        device_type = alarm.metadata.get("device_type")
        if device_type:
            point = point.tag("device_type", device_type)

        # Add rule_name tag from alarm metadata if available (for display purposes)
        rule_name = alarm.metadata.get("rule_name")
        if rule_name:
            point = point.tag("rule_name", rule_name)

        # Add site_id tag if available
        point = self._add_site_tag(point, site_id, alarm.metadata)

        point = point.field("value", 1).time(alarm.timestamp)  # Alarm count

        if self.use_async:
            # Add to buffer for batch write
            self._write_buffer.append(point)
            if len(self._write_buffer) >= self.batch_size or flush:
                self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                self._write_buffer = []
        else:
            self.write_api.write(bucket=self.bucket, record=point)

    def write_bms_data(self, bms_data: BMSData, site_id: Optional[str] = None):
        """
        Write BMS data with multi-site support

        Args:
            bms_data: BMS data object
            site_id: Optional site ID for multi-site support
        """
        # Extract site_id from metadata if not provided
        metadata = getattr(bms_data, "metadata", None) or {}

        # Write SOC
        point_soc = (
            Point("bms_data").tag("pack_id", bms_data.pack_id).tag("metric", "soc")
        )
        point_soc = self._add_site_tag(point_soc, site_id, metadata)
        point_soc = point_soc.field("value", bms_data.soc).time(bms_data.timestamp)

        # Write SOH
        point_soh = (
            Point("bms_data").tag("pack_id", bms_data.pack_id).tag("metric", "soh")
        )
        point_soh = self._add_site_tag(point_soh, site_id, metadata)
        point_soh = point_soh.field("value", bms_data.soh).time(bms_data.timestamp)

        # Write maximum voltage difference
        point_delta_v = (
            Point("bms_data")
            .tag("pack_id", bms_data.pack_id)
            .tag("metric", "max_delta_v")
        )
        point_delta_v = self._add_site_tag(point_delta_v, site_id, metadata)
        point_delta_v = point_delta_v.field("value", bms_data.max_delta_v).time(
            bms_data.timestamp
        )

        # Write max/min voltage
        point_max_v = (
            Point("bms_data")
            .tag("pack_id", bms_data.pack_id)
            .tag("metric", "max_voltage")
        )
        point_max_v = self._add_site_tag(point_max_v, site_id, metadata)
        point_max_v = point_max_v.field("value", bms_data.max_voltage).time(
            bms_data.timestamp
        )

        point_min_v = (
            Point("bms_data")
            .tag("pack_id", bms_data.pack_id)
            .tag("metric", "min_voltage")
        )
        point_min_v = self._add_site_tag(point_min_v, site_id, metadata)
        point_min_v = point_min_v.field("value", bms_data.min_voltage).time(
            bms_data.timestamp
        )

        # Write max/min temperature
        point_max_t = (
            Point("bms_data")
            .tag("pack_id", bms_data.pack_id)
            .tag("metric", "max_temperature")
        )
        point_max_t = self._add_site_tag(point_max_t, site_id, metadata)
        point_max_t = point_max_t.field("value", bms_data.max_temperature).time(
            bms_data.timestamp
        )

        point_min_t = (
            Point("bms_data")
            .tag("pack_id", bms_data.pack_id)
            .tag("metric", "min_temperature")
        )
        point_min_t = self._add_site_tag(point_min_t, site_id, metadata)
        point_min_t = point_min_t.field("value", bms_data.min_temperature).time(
            bms_data.timestamp
        )

        # Batch write
        points = [
            point_soc,
            point_soh,
            point_delta_v,
            point_max_v,
            point_min_v,
            point_max_t,
            point_min_t,
        ]

        if self.use_async:
            self._write_buffer.extend(points)
            if len(self._write_buffer) >= self.batch_size:
                self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                self._write_buffer = []
        else:
            self.write_api.write(bucket=self.bucket, record=points)

    def write_device_data(self, device_data: DeviceData, flush: bool = False):
        """
        Write generic device data with multi-site support

        This method is fully flexible and automatically supports:
        - All known device types (BMS, PCS, UPS, TMS, etc.)
        - Any future/unknown device types (automatically detected)
        - All data fields (automatically extracted from device_data.data)
        - Multi-site support (via site_id tag)

        No need to create device-specific write methods - this handles everything!

        Args:
            device_data: DeviceData object (supports BMS, PCS, UPS, TMS, and any future types)
            flush: If True, immediately flush buffer
        """
        site_id = device_data.site_id
        device_type = device_data.device_type.value  # Automatically get device type
        device_id = device_data.device_id
        source = device_data.source or "unknown"

        # Write each data field as a separate point
        # Automatically handles all fields regardless of device type
        points = []
        for field_name, field_value in device_data.data.items():
            if field_value is None:
                continue

            # Create point with automatic device type detection
            point = (
                Point("device_data")
                .tag("device_id", device_id)
                .tag("device_type", device_type)  # Automatically uses detected type
                .tag("source", source)
                .tag("metric", field_name)  # Each field becomes a metric
            )

            # Add site_id tag if available
            if site_id:
                point = point.tag("site_id", site_id)

            # Add metadata as tags if available
            if device_data.metadata:
                for key, value in device_data.metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        point = point.tag(f"meta_{key}", str(value))

            # Handle different value types to prevent InfluxDB field type conflicts
            # InfluxDB requires consistent field types - strings should be tags, not fields
            if isinstance(field_value, (int, float)):
                # Numeric values go into the "value" field as float
                field_value_typed = float(field_value)
                point = point.field("value", field_value_typed)
            elif isinstance(field_value, bool):
                # Boolean values converted to float (0 or 1)
                field_value_typed = float(1 if field_value else 0)
                point = point.field("value", field_value_typed)
            elif isinstance(field_value, (list, dict)):
                # Complex types: store as tag (string representation)
                # This prevents field type conflicts
                import json

                field_value_str = json.dumps(field_value)
                point = point.tag(f"{field_name}_json", field_value_str)
                
                # Special handling for numeric arrays (e.g., cell_voltages, temperatures)
                # Store each element as a separate metric point for queryability
                if isinstance(field_value, list) and len(field_value) > 0:
                    # Check if all elements are numeric
                    if all(isinstance(item, (int, float)) for item in field_value):
                        # Store each element as a separate point with cell_index tag
                        # Get timestamp once for all cell points
                        timestamp = device_data.timestamp
                        if timestamp.tzinfo is None:
                            from datetime import UTC
                            timestamp = timestamp.replace(tzinfo=UTC)
                        else:
                            from datetime import UTC
                            if timestamp.tzinfo != UTC:
                                timestamp = timestamp.astimezone(UTC)
                        
                        for idx, item in enumerate(field_value):
                            cell_point = (
                                Point("device_data")
                                .tag("device_id", device_id)
                                .tag("device_type", device_type)
                                .tag("source", source)
                                .tag("metric", field_name)  # e.g., "cell_voltages"
                                .tag("cell_index", str(idx))  # Index within the array
                            )
                            if site_id:
                                cell_point = cell_point.tag("site_id", site_id)
                            if device_data.metadata:
                                for key, value in device_data.metadata.items():
                                    if isinstance(value, (str, int, float, bool)):
                                        cell_point = cell_point.tag(f"meta_{key}", str(value))
                            cell_point = cell_point.field("value", float(item)).time(timestamp)
                            points.append(cell_point)
                        
                        # Also store aggregate values (mean, max, min) for the array
                        mean_value = sum(field_value) / len(field_value)
                        max_value = max(field_value)
                        min_value = min(field_value)
                        
                        # Mean value point
                        mean_point = (
                            Point("device_data")
                            .tag("device_id", device_id)
                            .tag("device_type", device_type)
                            .tag("source", source)
                            .tag("metric", f"{field_name}_mean")
                        )
                        if site_id:
                            mean_point = mean_point.tag("site_id", site_id)
                        if device_data.metadata:
                            for key, value in device_data.metadata.items():
                                if isinstance(value, (str, int, float, bool)):
                                    mean_point = mean_point.tag(f"meta_{key}", str(value))
                        mean_point = mean_point.field("value", float(mean_value)).time(timestamp)
                        points.append(mean_point)
                        
                        # Max value point
                        max_point = (
                            Point("device_data")
                            .tag("device_id", device_id)
                            .tag("device_type", device_type)
                            .tag("source", source)
                            .tag("metric", f"{field_name}_max")
                        )
                        if site_id:
                            max_point = max_point.tag("site_id", site_id)
                        if device_data.metadata:
                            for key, value in device_data.metadata.items():
                                if isinstance(value, (str, int, float, bool)):
                                    max_point = max_point.tag(f"meta_{key}", str(value))
                        max_point = max_point.field("value", float(max_value)).time(timestamp)
                        points.append(max_point)
                        
                        # Min value point
                        min_point = (
                            Point("device_data")
                            .tag("device_id", device_id)
                            .tag("device_type", device_type)
                            .tag("source", source)
                            .tag("metric", f"{field_name}_min")
                        )
                        if site_id:
                            min_point = min_point.tag("site_id", site_id)
                        if device_data.metadata:
                            for key, value in device_data.metadata.items():
                                if isinstance(value, (str, int, float, bool)):
                                    min_point = min_point.tag(f"meta_{key}", str(value))
                        min_point = min_point.field("value", float(min_value)).time(timestamp)
                        points.append(min_point)
                        
                        # Skip the original point for numeric arrays (already stored as individual cells)
                        continue
                    else:
                        # Non-numeric array: store count as value
                        point = point.field("value", float(len(field_value)))
                else:
                    # For dict, skip numeric value or use 1 as placeholder
                    point = point.field("value", 1.0)
            elif isinstance(field_value, str):
                # String values: use as tag to avoid field type conflicts
                # InfluxDB doesn't allow mixing string and numeric in same field
                point = point.tag(f"{field_name}_str", field_value)
                # Use a placeholder numeric value (1.0) to indicate this metric exists
                point = point.field("value", 1.0)
            else:
                # Fallback: convert to string tag
                point = point.tag(f"{field_name}_str", str(field_value))
                point = point.field("value", 1.0)

            # Ensure timestamp is timezone-aware and in UTC
            timestamp = device_data.timestamp
            if timestamp.tzinfo is None:
                from datetime import UTC

                timestamp = timestamp.replace(tzinfo=UTC)
                logger.debug(
                    f"  [InfluxDB] Timestamp had no timezone, added UTC: {timestamp}"
                )
            else:
                from datetime import UTC

                if timestamp.tzinfo != UTC:
                    old_timestamp = timestamp
                    timestamp = timestamp.astimezone(UTC)
                    logger.debug(
                        f"  [InfluxDB] Converted timestamp from {old_timestamp} to UTC: {timestamp}"
                    )

            logger.debug(
                f"  [InfluxDB] Writing point for metric '{field_name}' with timestamp: {timestamp}"
            )
            point = point.time(timestamp)
            points.append(point)

        if self.use_async:
            self._write_buffer.extend(points)
            if len(self._write_buffer) >= self.batch_size or flush:
                logger.debug(
                    f"  [InfluxDB] Writing {len(self._write_buffer)} points to InfluxDB "
                    f"(batch_size={self.batch_size}, flush={flush})"
                )
                try:
                    self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                    logger.debug(
                        f"  ✓ [InfluxDB] Successfully wrote {len(self._write_buffer)} points"
                    )
                    self._write_buffer = []
                except Exception as e:
                    logger.error(
                        f"  ✗ [InfluxDB] Failed to write points: {e}", exc_info=True
                    )
                    raise
            else:
                logger.debug(
                    f"  [InfluxDB] Buffered {len(points)} points "
                    f"(total buffer: {len(self._write_buffer)}, will flush when buffer >= {self.batch_size})"
                )
        else:
            if points:
                logger.debug(
                    f"  [InfluxDB] Writing {len(points)} points to InfluxDB (sync mode, immediate write)"
                )
                try:
                    self.write_api.write(bucket=self.bucket, record=points)
                    logger.debug(
                        f"  ✓ [InfluxDB] Successfully wrote {len(points)} points to bucket '{self.bucket}'"
                    )
                except Exception as e:
                    logger.error(
                        f"  ✗ [InfluxDB] Failed to write points: {e}", exc_info=True
                    )
                    raise

    def write_diagnostic(
        self, alarm_id: str, diagnostic: Dict[str, Any], site_id: Optional[str] = None, flush: bool = False
    ):
        """
        Write diagnostic report with multi-site support

        Args:
            alarm_id: Alarm ID
            diagnostic: Diagnostic report dictionary
            site_id: Optional site ID
        """
        point = (
            Point("diagnostics")
            .tag("alarm_id", alarm_id)
            .tag("risk_level", diagnostic.get("risk_level", "Unknown"))
        )

        # Add device_id tag from diagnostic metadata if available
        device_id = diagnostic.get("metadata", {}).get("device_id")
        if device_id:
            point = point.tag("device_id", device_id)

        # Add alarm_type tag from diagnostic metadata if available
        alarm_type = diagnostic.get("metadata", {}).get("alarm_type")
        if alarm_type:
            point = point.tag("alarm_type", alarm_type)

        # Add device_type tag from diagnostic metadata if available
        # device_type is stored in diagnostic metadata from alarm metadata
        device_type = diagnostic.get("metadata", {}).get("device_type")
        if device_type:
            point = point.tag("device_type", device_type)

        if site_id:
            point = point.tag("site_id", site_id)
        elif diagnostic.get("metadata", {}).get("site_id"):
            point = point.tag("site_id", diagnostic["metadata"]["site_id"])

        # Store full diagnostic report as JSON field for retrieval
        import json
        from datetime import datetime, UTC
        
        # Create a copy of diagnostic dict and convert datetime objects to ISO strings for JSON serialization
        diagnostic_for_json = {}
        for key, value in diagnostic.items():
            if isinstance(value, datetime):
                diagnostic_for_json[key] = value.isoformat()
            elif isinstance(value, dict):
                # Recursively handle nested dicts
                nested_dict = {}
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, datetime):
                        nested_dict[nested_key] = nested_value.isoformat()
                    else:
                        nested_dict[nested_key] = nested_value
                diagnostic_for_json[key] = nested_dict
            elif isinstance(value, list):
                # Handle lists that might contain datetime objects
                nested_list = []
                for item in value:
                    if isinstance(item, datetime):
                        nested_list.append(item.isoformat())
                    elif isinstance(item, dict):
                        nested_dict = {}
                        for nested_key, nested_value in item.items():
                            if isinstance(nested_value, datetime):
                                nested_dict[nested_key] = nested_value.isoformat()
                            else:
                                nested_dict[nested_key] = nested_value
                        nested_list.append(nested_dict)
                    else:
                        nested_list.append(item)
                diagnostic_for_json[key] = nested_list
            else:
                diagnostic_for_json[key] = value
        
        diagnostic_json = json.dumps(diagnostic_for_json)
        
        # Get timestamp - handle both datetime objects and ISO strings
        timestamp = diagnostic.get("timestamp") or diagnostic.get("generated_at")
        if isinstance(timestamp, str):
            # Parse ISO string to datetime
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Fallback to current time if parsing fails
                timestamp = datetime.now(UTC)
        elif isinstance(timestamp, datetime):
            # Already a datetime object, use it
            pass
        elif timestamp is None:
            # No timestamp provided, use current time
            timestamp = datetime.now(UTC)
        
        # Ensure timestamp is timezone-aware and in UTC
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            elif timestamp.tzinfo != UTC:
                timestamp = timestamp.astimezone(UTC)
        
        point = (
            point.field("risk_level", diagnostic.get("risk_level", "Unknown"))
            .field("has_diagnostic", 1)
            .field("diagnostic_json", diagnostic_json)  # Store full diagnostic as JSON
            .time(timestamp)
        )

        if self.use_async:
            self._write_buffer.append(point)
            if len(self._write_buffer) >= self.batch_size or flush:
                self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                self._write_buffer = []
                if flush:
                    # Ensure data is flushed immediately
                    self.write_api.flush()
        else:
            self.write_api.write(bucket=self.bucket, record=point)
            if flush:
                # For sync mode, flush is handled by write_api
                pass

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

    def _get_bucket_for_query(self, site_id: Optional[str] = None) -> str:
        """
        Get bucket name for query based on site_id and container mode
        
        Args:
            site_id: Site ID (optional)
            
        Returns:
            Bucket name to use for query
        """
        # If site_id is provided and default bucket is "alarms", use site-specific bucket
        if site_id and self.bucket == "alarms":
            return f"site_{site_id}"
        return self.bucket

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
        """
        Query alarms from InfluxDB
        
        Args:
            start_time: Start time (RFC3339 format or relative time like "-1h")
            end_time: End time (RFC3339 format or relative time)
            alarm_id: Filter by alarm ID
            alarm_type: Filter by alarm type
            severity: Filter by severity (Info, Warning, Critical)
            source: Filter by source (BMS, PCS, EMS)
            site_id: Filter by site ID (also determines bucket in container mode)
            limit: Maximum number of results
            
        Returns:
            List of alarm dictionaries
        """
        if not INFLUXDB_AVAILABLE:
            return []
        
        try:
            # Get bucket name based on site_id and container mode
            bucket_name = self._get_bucket_for_query(site_id)
            logger.info(f"[InfluxDB] Querying alarms from bucket: {bucket_name}, site_id={site_id}, time_range={start_time}")
            
            # Build Flux query
            query = f'from(bucket: "{bucket_name}")'
            
            # Set time range - use start_time if provided, otherwise default to -30d
            if start_time:
                if end_time:
                    query += f' |> range(start: {start_time}, stop: {end_time})'
                else:
                    query += f' |> range(start: {start_time})'
            elif end_time:
                query += f' |> range(start: -30d, stop: {end_time})'
            else:
                query += ' |> range(start: -30d)'  # Default range
            
            query += ' |> filter(fn: (r) => r["_measurement"] == "alarms")'
            
            if alarm_id:
                query += f' |> filter(fn: (r) => r["alarm_id"] == "{alarm_id}")'
            if alarm_type:
                query += f' |> filter(fn: (r) => r["alarm_type"] == "{alarm_type}")'
            if severity:
                query += f' |> filter(fn: (r) => r["severity"] == "{severity}")'
            if source:
                query += f' |> filter(fn: (r) => r["source"] == "{source}")'
            if site_id:
                query += f' |> filter(fn: (r) => r["site_id"] == "{site_id}")'
            if device_type:
                query += f' |> filter(fn: (r) => r["device_type"] == "{device_type}")'
            
            query += ' |> sort(columns: ["_time"], desc: true)'
            query += f' |> limit(n: {limit})'
            
            # Execute query
            logger.debug(f"[InfluxDB] Executing alarm query: {query}")
            result = self.query_api.query(query=query, org=self.org)
            
            alarms = []
            record_count = 0
            for table in result:
                for record in table.records:
                    record_count += 1
                    alarm = {
                        "alarm_id": record.values.get("alarm_id", ""),
                        "alarm_type": record.values.get("alarm_type", ""),
                        "rule_name": record.values.get("rule_name", ""),  # Add rule_name for display
                        "severity": record.values.get("severity", ""),
                        "source": record.values.get("source", ""),
                        "device_id": record.values.get("device_id", ""),  # Add device_id
                        "device_type": record.values.get("device_type", ""),  # Add device_type
                        "timestamp": record.get_time().isoformat(),
                        "site_id": record.values.get("site_id"),
                        "alarm_level": record.values.get("alarm_level", "device_level"),  # Add alarm_level with default
                    }
                    alarms.append(alarm)
                    if len(alarms) == 1:  # Log first alarm as sample
                        logger.info(f"[InfluxDB] Sample alarm: alarm_id={alarm['alarm_id']}, alarm_type={alarm['alarm_type']}, site_id={alarm['site_id']}, device_id={alarm['device_id']}")
            
            logger.info(f"[InfluxDB] Query returned {record_count} records, {len(alarms)} alarms processed for site_id={site_id}")
            
            # If no alarms found with site_id filter, try querying without site_id filter to see if any alarms exist
            if len(alarms) == 0 and site_id:
                logger.warning(f"[InfluxDB] No alarms found with site_id={site_id} filter, trying without site_id filter...")
                # Try querying default bucket without site_id filter
                default_bucket = self.bucket if self.bucket != "alarms" else "alarms"
                fallback_query = f'from(bucket: "{default_bucket}")'
                if start_time:
                    if end_time:
                        fallback_query += f' |> range(start: {start_time}, stop: {end_time})'
                    else:
                        fallback_query += f' |> range(start: {start_time})'
                else:
                    fallback_query += ' |> range(start: -30d)'
                fallback_query += ' |> filter(fn: (r) => r["_measurement"] == "alarms")'
                fallback_query += ' |> sort(columns: ["_time"], desc: true)'
                fallback_query += f' |> limit(n: {limit})'
                
                try:
                    fallback_result = self.query_api.query(query=fallback_query, org=self.org)
                    fallback_count = 0
                    for table in fallback_result:
                        for record in table.records:
                            fallback_count += 1
                            record_site_id = record.values.get("site_id")
                            logger.info(f"[InfluxDB] Found alarm in fallback query: alarm_id={record.values.get('alarm_id')}, site_id={record_site_id}, bucket={default_bucket}")
                    if fallback_count > 0:
                        logger.warning(f"[InfluxDB] Found {fallback_count} alarms in fallback query, but site_id filter may be incorrect")
                except Exception as e:
                    logger.debug(f"[InfluxDB] Fallback query failed: {e}")
            
            return alarms
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                logger.error(
                    f"InfluxDB authentication failed. Please check INFLUXDB_TOKEN. "
                    f"Run 'python scripts/setup_influxdb.py' to set up InfluxDB. Error: {e}"
                )
            else:
                logger.error(f"Failed to query alarms: {e}", exc_info=True)
            return []
    
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
        """
        Query diagnostic reports from InfluxDB
        
        Args:
            start_time: Start time (RFC3339 format or relative time)
            end_time: End time (RFC3339 format or relative time)
            alarm_id: Filter by alarm ID
            risk_level: Filter by risk level (Low, Medium, High)
            site_id: Filter by site ID
            limit: Maximum number of results
            
        Returns:
            List of diagnostic report dictionaries
        """
        if not INFLUXDB_AVAILABLE:
            return []
        
        try:
            # Get bucket name based on site_id and container mode
            bucket_name = self._get_bucket_for_query(site_id)
            
            # Build Flux query
            query = f'from(bucket: "{bucket_name}")'
            query += ' |> range(start: -30d)'
            
            if start_time:
                query += f' |> range(start: {start_time}'
                if end_time:
                    query += f', stop: {end_time}'
                query += ')'
            elif end_time:
                query += f' |> range(start: -30d, stop: {end_time})'
            
            query += ' |> filter(fn: (r) => r["_measurement"] == "diagnostics")'
            
            if alarm_id:
                query += f' |> filter(fn: (r) => r["alarm_id"] == "{alarm_id}")'
            if risk_level:
                query += f' |> filter(fn: (r) => r["risk_level"] == "{risk_level}")'
            if site_id:
                query += f' |> filter(fn: (r) => r["site_id"] == "{site_id}")'
            if device_type:
                query += f' |> filter(fn: (r) => r["device_type"] == "{device_type}")'
            
            query += ' |> sort(columns: ["_time"], desc: true)'
            query += f' |> limit(n: {limit})'
            
            # Execute query
            result = self.query_api.query(query=query, org=self.org)
            
            # Group records by time and tags to reconstruct diagnostic objects
            # In InfluxDB, each field is a separate record, so we need to group them
            diagnostics_dict = {}
            
            for table in result:
                for record in table.records:
                    # Use alarm_id + timestamp as key to group records
                    alarm_id = record.values.get("alarm_id", "")
                    timestamp = record.get_time().isoformat()
                    key = f"{alarm_id}_{timestamp}"
                    
                    if key not in diagnostics_dict:
                        diagnostics_dict[key] = {
                            "alarm_id": alarm_id,
                            "risk_level": "",
                            "device_id": record.values.get("device_id", ""),
                            "alarm_type": record.values.get("alarm_type", ""),
                            "timestamp": timestamp,
                            "site_id": record.values.get("site_id"),
                            "diagnostic_json": None,
                        }
                    
                    # Get field name and value
                    field_name = record.values.get("_field")
                    field_value = record.get_value()
                    
                    # Store field values
                    if field_name == "risk_level":
                        diagnostics_dict[key]["risk_level"] = field_value
                    elif field_name == "diagnostic_json":
                        diagnostics_dict[key]["diagnostic_json"] = field_value
            
            # Convert to list and parse JSON
            diagnostics = []
            for key, diagnostic in diagnostics_dict.items():
                # Try to parse full diagnostic from JSON field
                diagnostic_json = diagnostic.get("diagnostic_json")
                if diagnostic_json:
                    try:
                        import json
                        full_diagnostic = json.loads(diagnostic_json)
                        # Merge full diagnostic data into result
                        diagnostic.update({
                            "current_status": full_diagnostic.get("current_status", ""),
                            "possible_causes": full_diagnostic.get("possible_causes", []),
                            "recommended_actions": full_diagnostic.get("recommended_actions", []),
                            "references": full_diagnostic.get("references", []),
                            "markdown": full_diagnostic.get("markdown", ""),
                            "generated_at": full_diagnostic.get("generated_at", diagnostic.get("timestamp")),
                        })
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse diagnostic JSON for alarm {diagnostic.get('alarm_id')}: {e}")
                
                # Remove diagnostic_json from output
                diagnostic.pop("diagnostic_json", None)
                diagnostics.append(diagnostic)
            
            return diagnostics
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                logger.error(
                    f"InfluxDB authentication failed. Please check INFLUXDB_TOKEN. "
                    f"Run 'python scripts/setup_influxdb.py' to set up InfluxDB. Error: {e}"
                )
            else:
                logger.error(f"Failed to query diagnostics: {e}", exc_info=True)
            return []
    
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
        """
        Query time series metrics aggregated by time interval
        
        Args:
            start_time: Start time (RFC3339 format or relative time like "-24h")
            end_time: End time (RFC3339 format)
            interval: Time interval for aggregation (e.g., "1h", "1d", "5m")
            metric_type: Type of metric ("alarms", "diagnostics", "devices")
            group_by: Optional field to group by (e.g., "severity", "risk_level")
            site_id: Site ID for container mode (optional)
            limit: Maximum number of results
            
        Returns:
            List of time series data points with timestamp and values
        """
        if not INFLUXDB_AVAILABLE:
            return []
        
        try:
            # Default to last 24 hours if not specified
            if not start_time:
                start_time = "-24h"
            
            # Get bucket name based on site_id and container mode
            bucket_name = self._get_bucket_for_query(site_id)
            
            # Build Flux query
            query = f'from(bucket: "{bucket_name}")'
            query += f' |> range(start: {start_time}'
            if end_time:
                query += f', stop: {end_time}'
            query += ')'
            
            # Filter by measurement type
            if metric_type == "alarms":
                query += ' |> filter(fn: (r) => r["_measurement"] == "alarms")'
            elif metric_type == "diagnostics":
                query += ' |> filter(fn: (r) => r["_measurement"] == "diagnostics")'
            elif metric_type == "devices":
                query += ' |> filter(fn: (r) => r["_measurement"] == "device_data")'
            
            # Group by specified field if provided
            if group_by:
                query += f' |> group(columns: ["{group_by}"])'
            
            # Aggregate by time window
            query += f' |> aggregateWindow(every: {interval}, fn: count, createEmpty: false)'
            
            # Sort by time
            query += ' |> sort(columns: ["_time"])'
            query += f' |> limit(n: {limit})'
            
            # Execute query
            result = self.query_api.query(query=query, org=self.org)
            
            time_series = []
            for table in result:
                for record in table.records:
                    time_point = {
                        "timestamp": record.get_time().isoformat(),
                        "value": record.get_value(),
                    }
                    
                    # Add group_by field if present
                    if group_by and hasattr(record, "values"):
                        time_point[group_by] = record.values.get(group_by)
                    
                    # Add other relevant fields
                    if hasattr(record, "values"):
                        for key in ["severity", "risk_level", "alarm_type", "source", "site_id"]:
                            if key in record.values:
                                time_point[key] = record.values[key]
                    
                    time_series.append(time_point)
            
            return time_series
        except Exception as e:
            logger.error(f"Failed to query time series metrics: {e}", exc_info=True)
            return []
    
    def query_device_time_series(
        self,
        device_ids: Optional[List[str]] = None,
        site_id: Optional[str] = None,
        device_type: Optional[str] = None,
        metric: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        interval: str = "5m",  # "5m", "1h", "1d", etc.
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query device time series data from MQTT/device_data
        
        Args:
            device_ids: List of device IDs to filter by
            site_id: Site ID to filter by
            device_type: Device type to filter by (BMS, PCS, etc.)
            metric: Metric name to filter by (soc, voltage, etc.)
            start_time: Start time (RFC3339 format or relative time like "-24h")
            end_time: End time (RFC3339 format)
            interval: Time interval for aggregation (e.g., "5m", "1h", "1d")
            limit: Maximum number of results
            
        Returns:
            List of time series data points with device_id, metric, timestamp, and value
        """
        if not INFLUXDB_AVAILABLE:
            return []
        
        try:
            # Default to last 24 hours if not specified
            if not start_time:
                start_time = "-24h"
            
            # Get bucket name based on site_id and container mode
            bucket_name = self._get_bucket_for_query(site_id)
            
            # Build Flux query
            query = f'from(bucket: "{bucket_name}")'
            query += f' |> range(start: {start_time}'
            if end_time:
                query += f', stop: {end_time}'
            query += ')'
            
            # Filter by measurement
            query += ' |> filter(fn: (r) => r["_measurement"] == "device_data")'
            
            # Filter by device_id(s)
            if device_ids:
                if len(device_ids) == 1:
                    query += f' |> filter(fn: (r) => r["device_id"] == "{device_ids[0]}")'
                else:
                    device_ids_str = '", "'.join(device_ids)
                    query += f' |> filter(fn: (r) => contains(value: r["device_id"], set: ["{device_ids_str}"]))'
            
            # Filter by site_id (try both exact match and flexible matching)
            # Note: site_id might be stored as "1" but data has "SITE_001" or vice versa
            if site_id:
                # Build flexible site_id filter
                site_filters = [f'r["site_id"] == "{site_id}"']
                
                # Try matching with SITE_ prefix if site_id is numeric
                if site_id.isdigit():
                    site_filters.append(f'r["site_id"] == "SITE_{site_id.zfill(3)}"')
                # Try matching without SITE_ prefix if site_id starts with SITE_
                elif site_id.startswith("SITE_"):
                    numeric_part = site_id.replace("SITE_", "").lstrip("0") or "0"
                    site_filters.append(f'r["site_id"] == "{numeric_part}"')
                
                # Also check meta_site_id
                site_filters.append(f'r["meta_site_id"] == "{site_id}"')
                
                query += f' |> filter(fn: (r) => {" or ".join(site_filters)})'
            
            # Filter by device_type
            if device_type:
                query += f' |> filter(fn: (r) => r["device_type"] == "{device_type}")'
            
            # Filter by metric
            if metric:
                query += f' |> filter(fn: (r) => r["metric"] == "{metric}")'
            
            # Filter to only numeric fields before aggregation
            # mean() only works on numeric values, not strings
            # aggregateWindow with mean() will automatically skip non-numeric values
            # We just need to ensure _value exists
            query += ' |> filter(fn: (r) => exists r._value)'
            
            # Group by device_id and metric to aggregate separately
            # Always group by device_id if filtering by device_ids (even for single device)
            # This ensures device_id is preserved in the result
            group_columns = []
            if device_ids:
                group_columns.append("device_id")
            if not metric:
                group_columns.append("metric")
            if group_columns:
                columns_str = ', '.join([f'"{col}"' for col in group_columns])
                query += f' |> group(columns: [{columns_str}])'
            
            # Before aggregation, map to ensure only _value field is kept
            # This prevents aggregateWindow from trying to aggregate string fields
            # Keep only essential columns: _time, _value, and grouping columns
            # Always keep device_id if filtering by device_ids (even for single device)
            keep_cols = ["_time", "_value"]
            if device_ids:
                keep_cols.append("device_id")
            if not metric:
                keep_cols.append("metric")
            keep_cols_str = ', '.join([f'"{col}"' for col in keep_cols])
            query += f' |> keep(columns: [{keep_cols_str}])'
            
            # Aggregate by time window (only on numeric _value field)
            query += f' |> aggregateWindow(every: {interval}, fn: mean, createEmpty: false)'
            
            # Sort by time
            query += ' |> sort(columns: ["_time"])'
            query += f' |> limit(n: {limit})'
            
            # Execute query
            logger.debug(f"[InfluxDB] Executing device time series query: {query}")
            result = self.query_api.query(query=query, org=self.org)
            
            time_series = []
            record_count = 0
            for table in result:
                for record in table.records:
                    record_count += 1
                    time_point = {
                        "timestamp": record.get_time().isoformat(),
                        "value": record.get_value(),
                    }
                    
                    # Add device and metric info
                    if hasattr(record, "values"):
                        for key in ["device_id", "metric", "device_type", "site_id"]:
                            if key in record.values:
                                time_point[key] = record.values[key]
                    
                    time_series.append(time_point)
            
            logger.info(f"[InfluxDB] Query returned {record_count} records, {len(time_series)} time series points")
            if record_count == 0:
                # This is normal when:
                # 1. User selects a device that doesn't exist or has no data
                # 2. Time range has no data
                # 3. Device was removed but still selected in UI
                # Use debug level instead of warning to avoid noise
                logger.debug(f"[InfluxDB] No data found for query with params: device_ids={device_ids}, site_id={site_id}, metric={metric}")
            
            return time_series
        except Exception as e:
            logger.error(f"Failed to query device time series: {e}", exc_info=True)
            return []
    
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
