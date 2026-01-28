"""
InfluxDB querier module
Handles all query operations (alarms, diagnostics, device data, time series)
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False


class InfluxDBQuerier:
    """Handles all InfluxDB query operations"""

    def __init__(self, client):
        """
        Initialize querier with InfluxDB client
        
        Args:
            client: InfluxDBClient instance (provides query_api, bucket, org, etc.)
        """
        self.client = client
        self.query_api = client.query_api
        self.bucket = client.bucket
        self.org = client.org

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
            device_type: Filter by device type
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
            if "could not find bucket" in error_msg or (
                "not found" in error_msg.lower() and "bucket" in error_msg.lower()
            ):
                # Default bucket "alarms" is ensured at startup; log at DEBUG to avoid spam when it is missing
                level = logger.debug if bucket_name == "alarms" else logger.warning
                level(
                    "InfluxDB bucket '%s' not found, returning empty alarms. "
                    "Create the bucket or run setup_influxdb if needed.",
                    bucket_name,
                )
                return []
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
            if "could not find bucket" in error_msg or (
                "not found" in error_msg.lower() and "bucket" in error_msg.lower()
            ):
                # Default bucket "alarms" is ensured at startup; log at DEBUG to avoid spam when it is missing
                level = logger.debug if bucket_name == "alarms" else logger.warning
                level(
                    "InfluxDB bucket '%s' not found, returning empty diagnostics. "
                    "Create the bucket or run setup_influxdb if needed.",
                    bucket_name,
                )
                return []
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
        interval: str = "1m",  # "1m", "5m", "1h", "1d", etc.
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
