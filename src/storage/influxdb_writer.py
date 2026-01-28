"""
InfluxDB writer module
Handles all write operations (alarms, device data, diagnostics, BMS data)
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from influxdb_client import Point
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    Point = type("Point", (), {})

from ..models.alarm import Alarm
from ..models.device_data import DeviceData

# Try to import BMSData from integration module
try:
    from ..integrations.bms import BMSData
except ImportError:
    BMSData = None


class InfluxDBWriter:
    """Handles all InfluxDB write operations"""

    def __init__(self, client):
        """
        Initialize writer with InfluxDB client
        
        Args:
            client: InfluxDBClient instance (provides write_api, bucket, etc.)
        """
        self.client = client
        self.write_api = client.write_api
        self.bucket = client.bucket
        self.org = client.org
        self.use_async = client.use_async
        self.batch_size = client.batch_size
        self._write_buffer = client._write_buffer

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
        Only keeps the latest snapshot for each alarm type (and device_id if present)
        
        Args:
            alarm: Alarm object
            flush: If True, immediately flush buffer (default: False, batch write)
            site_id: Optional site ID for multi-site support
        """
        # Delete old alarms of the same type before writing new one
        if INFLUXDB_AVAILABLE:
            try:
                from datetime import datetime, timedelta, UTC
                
                device_id = alarm.metadata.get("device_id")
                
                delete_api = self.client.client.delete_api()
                
                # Delete from last 90 days to future (covers all recent alarms)
                start_time = datetime.now(UTC) - timedelta(days=90)
                stop_time = datetime.now(UTC) + timedelta(days=1)
                
                # Build predicate to match alarm_type and device_id (if present)
                predicate = '_measurement="alarms"'
                predicate += f' AND alarm_type="{alarm.alarm_type}"'
                
                if device_id:
                    predicate += f' AND device_id="{device_id}"'
                
                # Add site_id to predicate if available
                if site_id:
                    predicate += f' AND site_id="{site_id}"'
                elif alarm.metadata.get("site_id"):
                    predicate += f' AND site_id="{alarm.metadata.get("site_id")}"'
                
                try:
                    delete_api.delete(
                        start=start_time,
                        stop=stop_time,
                        predicate=predicate,
                        bucket=self.bucket,
                        org=self.org
                    )
                    logger.debug(f"Deleted old alarm(s) of type {alarm.alarm_type} "
                               f"{f'for device {device_id}' if device_id else ''} before writing new snapshot")
                except Exception as e:
                    logger.warning(f"Failed to delete old alarms before writing new one: {e}")
            except Exception as e:
                logger.warning(f"Error deleting old alarms: {e}")
        
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

        # Add rule_name tag from alarm metadata if available
        rule_name = alarm.metadata.get("rule_name")
        if rule_name:
            point = point.tag("rule_name", rule_name)

        # Add site_id tag if available
        point = self._add_site_tag(point, site_id, alarm.metadata)

        point = point.field("value", 1).time(alarm.timestamp)

        if self.use_async:
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
        if BMSData is None:
            logger.warning("BMSData not available, skipping write")
            return
        
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
        
        Args:
            device_data: DeviceData object (supports BMS, PCS, UPS, TMS, and any future types)
            flush: If True, immediately flush buffer
        """
        site_id = device_data.site_id
        device_type = device_data.device_type.value
        device_id = device_data.device_id
        source = device_data.source or "unknown"

        # Write each data field as a separate point
        points = []
        for field_name, field_value in device_data.data.items():
            if field_value is None:
                continue

            # Create point with automatic device type detection
            point = (
                Point("device_data")
                .tag("device_id", device_id)
                .tag("device_type", device_type)
                .tag("source", source)
                .tag("metric", field_name)
            )

            # Add site_id tag if available
            if site_id:
                point = point.tag("site_id", site_id)

            # Add metadata as tags if available
            if device_data.metadata:
                for key, value in device_data.metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        point = point.tag(f"meta_{key}", str(value))

            # Handle different value types
            if isinstance(field_value, (int, float)):
                field_value_typed = float(field_value)
                point = point.field("value", field_value_typed)
            elif isinstance(field_value, bool):
                field_value_typed = float(1 if field_value else 0)
                point = point.field("value", field_value_typed)
            elif isinstance(field_value, (list, dict)):
                import json
                field_value_str = json.dumps(field_value)
                point = point.tag(f"{field_name}_json", field_value_str)
                
                # Special handling for numeric arrays
                if isinstance(field_value, list) and len(field_value) > 0:
                    if all(isinstance(item, (int, float)) for item in field_value):
                        from datetime import UTC
                        timestamp = device_data.timestamp
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=UTC)
                        else:
                            if timestamp.tzinfo != UTC:
                                timestamp = timestamp.astimezone(UTC)
                        
                        for idx, item in enumerate(field_value):
                            cell_point = (
                                Point("device_data")
                                .tag("device_id", device_id)
                                .tag("device_type", device_type)
                                .tag("source", source)
                                .tag("metric", field_name)
                                .tag("cell_index", str(idx))
                            )
                            if site_id:
                                cell_point = cell_point.tag("site_id", site_id)
                            if device_data.metadata:
                                for key, value in device_data.metadata.items():
                                    if isinstance(value, (str, int, float, bool)):
                                        cell_point = cell_point.tag(f"meta_{key}", str(value))
                            cell_point = cell_point.field("value", float(item)).time(timestamp)
                            points.append(cell_point)
                        
                        # Store aggregate values (mean, max, min)
                        mean_value = sum(field_value) / len(field_value)
                        max_value = max(field_value)
                        min_value = min(field_value)
                        
                        for agg_name, agg_value in [("mean", mean_value), ("max", max_value), ("min", min_value)]:
                            agg_point = (
                                Point("device_data")
                                .tag("device_id", device_id)
                                .tag("device_type", device_type)
                                .tag("source", source)
                                .tag("metric", f"{field_name}_{agg_name}")
                            )
                            if site_id:
                                agg_point = agg_point.tag("site_id", site_id)
                            if device_data.metadata:
                                for key, value in device_data.metadata.items():
                                    if isinstance(value, (str, int, float, bool)):
                                        agg_point = agg_point.tag(f"meta_{key}", str(value))
                            agg_point = agg_point.field("value", float(agg_value)).time(timestamp)
                            points.append(agg_point)
                        
                        continue
                    else:
                        point = point.field("value", float(len(field_value)))
                else:
                    point = point.field("value", 1.0)
            elif isinstance(field_value, str):
                point = point.tag(f"{field_name}_str", field_value)
                point = point.field("value", 1.0)
            else:
                point = point.tag(f"{field_name}_str", str(field_value))
                point = point.field("value", 1.0)

            # Ensure timestamp is timezone-aware and in UTC
            timestamp = device_data.timestamp
            if timestamp.tzinfo is None:
                from datetime import UTC
                timestamp = timestamp.replace(tzinfo=UTC)
                logger.debug(f"  [InfluxDB] Timestamp had no timezone, added UTC: {timestamp}")
            else:
                from datetime import UTC
                if timestamp.tzinfo != UTC:
                    old_timestamp = timestamp
                    timestamp = timestamp.astimezone(UTC)
                    logger.debug(f"  [InfluxDB] Converted timestamp from {old_timestamp} to UTC: {timestamp}")

            logger.debug(f"  [InfluxDB] Writing point for metric '{field_name}' with timestamp: {timestamp}")
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
                    logger.debug(f"  ✓ [InfluxDB] Successfully wrote {len(self._write_buffer)} points")
                    self._write_buffer = []
                except Exception as e:
                    logger.error(f"  ✗ [InfluxDB] Failed to write points: {e}", exc_info=True)
                    raise
            else:
                logger.debug(
                    f"  [InfluxDB] Buffered {len(points)} points "
                    f"(total buffer: {len(self._write_buffer)}, will flush when buffer >= {self.batch_size})"
                )
        else:
            if points:
                logger.debug(f"  [InfluxDB] Writing {len(points)} points to InfluxDB (sync mode, immediate write)")
                try:
                    self.write_api.write(bucket=self.bucket, record=points)
                    logger.debug(f"  ✓ [InfluxDB] Successfully wrote {len(points)} points to bucket '{self.bucket}'")
                except Exception as e:
                    logger.error(f"  ✗ [InfluxDB] Failed to write points: {e}", exc_info=True)
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
            flush: If True, immediately flush buffer
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
        device_type = diagnostic.get("metadata", {}).get("device_type")
        if device_type:
            point = point.tag("device_type", device_type)

        if site_id:
            point = point.tag("site_id", site_id)
        elif diagnostic.get("metadata", {}).get("site_id"):
            point = point.tag("site_id", diagnostic["metadata"]["site_id"])

        # Store full diagnostic report as JSON field
        import json
        from datetime import datetime, UTC
        
        # Create a copy of diagnostic dict and convert datetime objects to ISO strings
        diagnostic_for_json = {}
        for key, value in diagnostic.items():
            if isinstance(value, datetime):
                diagnostic_for_json[key] = value.isoformat()
            elif isinstance(value, dict):
                nested_dict = {}
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, datetime):
                        nested_dict[nested_key] = nested_value.isoformat()
                    else:
                        nested_dict[nested_key] = nested_value
                diagnostic_for_json[key] = nested_dict
            elif isinstance(value, list):
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
        
        # Get timestamp
        timestamp = diagnostic.get("timestamp") or diagnostic.get("generated_at")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.now(UTC)
        elif isinstance(timestamp, datetime):
            pass
        elif timestamp is None:
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
            .field("diagnostic_json", diagnostic_json)
            .time(timestamp)
        )

        if self.use_async:
            self._write_buffer.append(point)
            if len(self._write_buffer) >= self.batch_size or flush:
                self.write_api.write(bucket=self.bucket, record=self._write_buffer)
                self._write_buffer = []
                if flush:
                    self.write_api.flush()
        else:
            self.write_api.write(bucket=self.bucket, record=point)
            if flush:
                pass
