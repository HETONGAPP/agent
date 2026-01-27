"""
Site Container - Containerized data management per site
Each site has its own isolated data container (InfluxDB bucket)
Provides clean data isolation, easy deletion, and independent management
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .influxdb_client import InfluxDBClient
from ..models.alarm import Alarm
from ..models.device_data import DeviceData

logger = logging.getLogger(__name__)


class SiteContainer:
    """
    Site-specific data container
    Each site has its own InfluxDB bucket for complete data isolation
    """

    def __init__(
        self,
        site_id: str,
        influx_client_base: InfluxDBClient,
        auto_create_bucket: bool = True,
    ):
        """
        Initialize site container

        Args:
            site_id: Site ID
            influx_client_base: Base InfluxDB client (for connection and bucket management)
            auto_create_bucket: Automatically create bucket if it doesn't exist
        """
        self.site_id = site_id
        self.bucket = f"site_{site_id}"  # Site-specific bucket name
        self.influx_client_base = influx_client_base

        # Create site-specific InfluxDB client with site bucket
        # Get pool_max_connections if available, otherwise use default
        pool_max_connections = getattr(influx_client_base, 'pool_max_connections', 5)
        use_connection_pool = getattr(influx_client_base, 'use_connection_pool', True)
        
        self.influx_client = InfluxDBClient(
            url=influx_client_base.url,
            token=influx_client_base.token,
            org=influx_client_base.org,
            bucket=self.bucket,
            use_async=getattr(influx_client_base, 'use_async', False),
            batch_size=getattr(influx_client_base, 'batch_size', 100),
            use_connection_pool=use_connection_pool,
            pool_max_connections=pool_max_connections,
        )

        # Create bucket if it doesn't exist
        if auto_create_bucket:
            self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure site bucket exists, create if it doesn't"""
        try:
            buckets_api = self.influx_client_base.client.buckets_api()
            
            # Check if bucket exists
            try:
                buckets = buckets_api.find_buckets()
                # buckets might be a Buckets object or a list, handle both
                if hasattr(buckets, 'buckets'):
                    bucket_list = buckets.buckets
                elif isinstance(buckets, list):
                    bucket_list = buckets
                else:
                    # Try to iterate directly
                    bucket_list = list(buckets) if buckets else []
                
                bucket_exists = any(b.name == self.bucket for b in bucket_list)
            except Exception:
                # If we can't check, try to create anyway (will fail if exists)
                bucket_exists = False
            
            if not bucket_exists:
                # Create bucket - use org name, InfluxDB will resolve to org ID
                # Get org ID from org name
                orgs_api = self.influx_client_base.client.organizations_api()
                orgs = orgs_api.find_organizations()
                org_id = None
                if hasattr(orgs, 'orgs'):
                    org_list = orgs.orgs
                elif isinstance(orgs, list):
                    org_list = orgs
                else:
                    org_list = list(orgs) if orgs else []
                
                for org in org_list:
                    if org.name == self.influx_client_base.org:
                        org_id = org.id
                        break
                
                if not org_id:
                    # Fallback: try to create with org name (some versions support this)
                    org_id = self.influx_client_base.org
                
                # Create bucket with retention policy
                from influxdb_client.domain.bucket import Bucket
                from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
                from ..storage.optimization_config import OptimizationConfig
                
                # Set retention policy: 30 days for raw data (can be overridden by downsampling)
                retention_seconds = OptimizationConfig.get_retention_seconds(
                    OptimizationConfig.RAW_DATA_RETENTION_DAYS
                )
                retention_rules = BucketRetentionRules(type="expire", every_seconds=retention_seconds)
                bucket = Bucket(
                    name=self.bucket,
                    org_id=org_id,
                    retention_rules=[retention_rules],
                )
                bucket = buckets_api.create_bucket(bucket=bucket)
                logger.info(f"✓ Created bucket for site {self.site_id}: {self.bucket} "
                          f"(retention: {OptimizationConfig.RAW_DATA_RETENTION_DAYS} days)")
            else:
                # Bucket already exists - this could happen if:
                # 1. Site was deleted and recreated quickly (bucket deletion might be delayed)
                # 2. Bucket was created manually
                # To ensure clean state, delete and recreate the bucket
                logger.warning(
                    f"Bucket for site {self.site_id} already exists: {self.bucket}. "
                    f"This might be from a previous site with the same ID. "
                    f"Deleting and recreating bucket to ensure clean state."
                )
                try:
                    # Get org ID for bucket recreation
                    orgs_api = self.influx_client_base.client.organizations_api()
                    orgs = orgs_api.find_organizations()
                    org_id = None
                    if hasattr(orgs, 'orgs'):
                        org_list = orgs.orgs
                    elif isinstance(orgs, list):
                        org_list = orgs
                    else:
                        org_list = list(orgs) if orgs else []
                    
                    for org in org_list:
                        if org.name == self.influx_client_base.org:
                            org_id = org.id
                            break
                    
                    if not org_id:
                        org_id = self.influx_client_base.org
                    
                    # Find and delete the existing bucket
                    bucket_obj = next((b for b in bucket_list if b.name == self.bucket), None)
                    if bucket_obj:
                        buckets_api.delete_bucket(bucket_obj)
                        logger.info(f"✓ Deleted existing bucket for site {self.site_id}")
                    
                    # Recreate bucket with clean state
                    from influxdb_client.domain.bucket import Bucket
                    from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
                    from ..storage.optimization_config import OptimizationConfig
                    
                    retention_seconds = OptimizationConfig.get_retention_seconds(
                        OptimizationConfig.RAW_DATA_RETENTION_DAYS
                    )
                    retention_rules = BucketRetentionRules(type="expire", every_seconds=retention_seconds)
                    bucket = Bucket(
                        name=self.bucket,
                        org_id=org_id,
                        retention_rules=[retention_rules],
                    )
                    bucket = buckets_api.create_bucket(bucket=bucket)
                    logger.info(f"✓ Recreated bucket for site {self.site_id}: {self.bucket} "
                              f"(retention: {OptimizationConfig.RAW_DATA_RETENTION_DAYS} days)")
                except Exception as recreate_error:
                    logger.error(f"Failed to recreate bucket for site {self.site_id}: {recreate_error}", exc_info=True)
                    raise
        except Exception as e:
            logger.warning(f"Failed to create bucket for site {self.site_id}: {e}")

    # ==================== Alarm Operations ====================
    
    def write_alarm(self, alarm: Alarm, flush: bool = False):
        """
        Write alarm to site container
        Only keeps the latest snapshot for each alarm type (and device_id if present)
        Note: The deletion of old alarms is handled by InfluxDBClient.write_alarm()
        """
        # Pass site_id to ensure it's stored correctly
        # The deletion of old alarms is handled in InfluxDBClient.write_alarm()
        return self.influx_client.write_alarm(alarm, flush=flush, site_id=self.site_id)

    def query_alarms(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        alarm_type: Optional[str] = None,
        severity: Optional[str] = None,
        device_type: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        limit: int = 100,
        deduplicate: bool = False,  # Disabled by default - return all alarms
    ) -> List[Dict[str, Any]]:
        """
        Query alarms from site container - no caching, no deduplication by default
        Returns all alarms matching the criteria directly from InfluxDB
        """
        alarms = self.influx_client.query_alarms(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            severity=severity,
            device_type=device_type,
            limit=limit,
        )
        # Filter by device_ids if provided
        if device_ids:
            alarms = [alarm for alarm in alarms if alarm.get("device_id") in device_ids]
        # Ensure all alarms have site_id set to this container's site_id
        for alarm in alarms:
            if not alarm.get("site_id"):
                alarm["site_id"] = self.site_id
        
        # Optional deduplication (disabled by default)
        if deduplicate and alarms:
            from datetime import datetime
            # Group by (device_id, alarm_type) and keep only the latest one
            alarm_groups: Dict[tuple, Dict[str, Any]] = {}
            for alarm in alarms:
                device_id = alarm.get("device_id", "")
                alarm_type_key = alarm.get("alarm_type", "")
                
                # Try to extract device_id from alarm_id if not present
                # Alarm ID format: {rule_id}_{device_id}_{timestamp} or similar
                if not device_id:
                    alarm_id = alarm.get("alarm_id", "")
                    if alarm_id and "_" in alarm_id:
                        parts = alarm_id.split("_")
                        if len(parts) >= 2:
                            # Try to find device_id in the parts (usually the second part)
                            for part in parts[1:]:  # Skip first part (rule_id)
                                # Check if this part looks like a device_id (contains letters/numbers)
                                if len(part) > 2 and any(c.isalpha() for c in part):
                                    device_id = part
                                    break
                
                # Use fallback values if missing to ensure alarms are not skipped
                if not device_id:
                    device_id = "UNKNOWN"
                if not alarm_type_key:
                    alarm_type_key = "UNKNOWN"
                
                key = (device_id, alarm_type_key)
                
                # Parse timestamp
                timestamp_str = alarm.get("timestamp", "")
                try:
                    if isinstance(timestamp_str, str):
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    else:
                        timestamp = timestamp_str
                except Exception:
                    # If timestamp parsing fails, skip this alarm
                    continue
                
                # Keep the latest alarm for this (device_id, alarm_type) combination
                if key not in alarm_groups:
                    alarm_groups[key] = alarm
                else:
                    existing_timestamp_str = alarm_groups[key].get("timestamp", "")
                    try:
                        if isinstance(existing_timestamp_str, str):
                            existing_timestamp = datetime.fromisoformat(existing_timestamp_str.replace("Z", "+00:00"))
                        else:
                            existing_timestamp = existing_timestamp_str
                        if timestamp > existing_timestamp:
                            alarm_groups[key] = alarm
                    except Exception:
                        # If timestamp comparison fails, keep existing
                        pass
            
            # Convert back to list and sort by timestamp (descending)
            alarms = list(alarm_groups.values())
            alarms.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            # Apply limit
            alarms = alarms[:limit]
        
        return alarms

    def delete_alarms(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_type: Optional[str] = None,
        alarm_id: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        rule_id: Optional[str] = None,
    ) -> int:
        """
        Delete alarms from site container
        
        Args:
            start_time: Start time for deletion (ISO format string)
            end_time: End time for deletion (ISO format string)
            alarm_type: Filter by alarm type
            alarm_id: Filter by specific alarm ID
            device_ids: Filter by device IDs
            rule_id: Filter by rule ID (new parameter)
        
        Returns:
            Number of alarms deleted
        """
        # Delete by querying and removing points
        # If rule_id is specified, use higher limit and wider time range to ensure we get all matching alarms
        query_limit = 50000 if rule_id else 10000
        # For rule_id deletion, use wider time range if not specified (last 90 days)
        if rule_id and not start_time:
            from datetime import datetime, timedelta, UTC
            rule_start_time = (datetime.now(UTC) - timedelta(days=90)).isoformat()
        else:
            rule_start_time = start_time
        alarms = self.query_alarms(
            start_time=rule_start_time if rule_id else start_time,
            end_time=end_time,
            alarm_type=alarm_type,
            alarm_id=alarm_id,
            device_ids=device_ids,
            limit=query_limit,
        )
        
        # Filter by rule_id if specified (rule_id is stored in metadata, or can be extracted from alarm_id)
        if rule_id and alarms:
            filtered_alarms = []
            for alarm in alarms:
                # Check metadata first
                alarm_rule_id = alarm.get("metadata", {}).get("rule_id") if isinstance(alarm.get("metadata"), dict) else None
                if alarm_rule_id == rule_id:
                    filtered_alarms.append(alarm)
                else:
                    # Also check alarm_id prefix (alarm_id format: {rule_id}_{device_id}_{timestamp})
                    alarm_id_str = alarm.get("alarm_id", "")
                    if alarm_id_str.startswith(f"{rule_id}_"):
                        filtered_alarms.append(alarm)
            alarms = filtered_alarms
        
        if not alarms:
            return 0
        
        # Delete using delete API
        try:
            delete_api = self.influx_client_base.client.delete_api()
            
            # Build delete predicate
            predicate = f'_measurement="alarms"'
            if alarm_type:
                predicate += f' AND alarm_type="{alarm_type}"'
            if alarm_id:
                predicate += f' AND alarm_id="{alarm_id}"'
            if device_ids:
                device_filter = " OR ".join([f'device_id="{d}"' for d in device_ids])
                predicate += f' AND ({device_filter})'
            # Note: rule_id is stored in metadata, so we need to query first and then delete by alarm_id
            # For now, we'll delete all matching alarms found in the query
            
            # Delete data
            from datetime import datetime, timedelta, UTC
            if start_time:
                start = start_time
            elif rule_id:
                # For rule_id deletion, use wider time range (90 days) to ensure we delete all related alarms
                start = datetime.now(UTC) - timedelta(days=90)
            else:
                start = datetime.now(UTC) - timedelta(days=30)
            
            if end_time:
                stop = end_time
            else:
                stop = datetime.now(UTC) + timedelta(days=1)
            
            # If rule_id is specified, delete by alarm_id prefix (more efficient than querying all)
            if rule_id:
                deleted_count = 0
                if alarms:
                    # Delete each alarm by its alarm_id (from query results)
                    for alarm in alarms:
                        alarm_id_to_delete = alarm.get("alarm_id")
                        if alarm_id_to_delete:
                            try:
                                delete_api.delete(
                                    start=start,
                                    stop=stop,
                                    predicate=f'_measurement="alarms" AND alarm_id="{alarm_id_to_delete}"',
                                    bucket=self.bucket,
                                    org=self.influx_client_base.org,
                                )
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete alarm {alarm_id_to_delete}: {e}")
                else:
                    # If no alarms found in query, try deleting by alarm_id prefix pattern
                    # This handles cases where query limit was reached or metadata doesn't match
                    # Note: InfluxDB doesn't support prefix matching directly, so we need to query first
                    # But we can use a more permissive query with alarm_type if available
                    logger.debug(f"No alarms found in query for rule_id {rule_id}, trying alternative deletion method")
                    # Re-query with higher limit and check alarm_id prefix
                    all_alarms = self.query_alarms(
                        start_time=start_time,
                        end_time=end_time,
                        limit=50000,  # Higher limit
                    )
                    for alarm in all_alarms:
                        alarm_id = alarm.get("alarm_id", "")
                        alarm_rule_id = alarm.get("metadata", {}).get("rule_id") if isinstance(alarm.get("metadata"), dict) else None
                        # Match by rule_id in metadata or alarm_id prefix
                        if alarm_rule_id == rule_id or alarm_id.startswith(f"{rule_id}_"):
                            alarm_id_to_delete = alarm.get("alarm_id")
                            if alarm_id_to_delete:
                                try:
                                    delete_api.delete(
                                        start=start,
                                        stop=stop,
                                        predicate=f'_measurement="alarms" AND alarm_id="{alarm_id_to_delete}"',
                                        bucket=self.bucket,
                                        org=self.influx_client_base.org,
                                    )
                                    deleted_count += 1
                                except Exception as e:
                                    logger.warning(f"Failed to delete alarm {alarm_id_to_delete}: {e}")
                logger.info(f"Deleted {deleted_count} alarms for rule {rule_id} from site {self.site_id}")
                return deleted_count
            else:
                # Standard deletion
                delete_api.delete(
                    start=start,
                    stop=stop,
                    predicate=predicate,
                    bucket=self.bucket,
                    org=self.influx_client_base.org,
                )
                
                deleted_count = len(alarms)
                logger.info(f"Deleted {deleted_count} alarms from site {self.site_id}")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete alarms from site {self.site_id}: {e}", exc_info=True)
            return 0

    # ==================== Diagnostic Operations ====================
    
    def write_diagnostic(self, alarm_id: str, diagnostic: Dict[str, Any], flush: bool = False):
        """Write diagnostic to site container"""
        # Pass site_id to ensure it's stored correctly
        result = self.influx_client.write_diagnostic(alarm_id, diagnostic, site_id=self.site_id, flush=flush)
        if flush:
            self.influx_client.flush()
        return result

    def query_diagnostics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        alarm_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        device_type: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
        limit: int = 100,
        deduplicate: bool = True,  # New parameter: deduplicate by (device_id, alarm_type)
    ) -> List[Dict[str, Any]]:
        """Query diagnostics from site container"""
        # Query more diagnostics if deduplication is enabled (to ensure we get the latest after dedup)
        query_limit = limit * 3 if deduplicate else limit
        diagnostics = self.influx_client.query_diagnostics(
            start_time=start_time,
            end_time=end_time,
            alarm_id=alarm_id,
            risk_level=risk_level,
            device_type=device_type,
            limit=query_limit,
        )
        # Filter by device_ids if provided
        if device_ids:
            diagnostics = [diag for diag in diagnostics if diag.get("device_id") in device_ids]
        # Ensure all diagnostics have site_id set to this container's site_id
        for diagnostic in diagnostics:
            if not diagnostic.get("site_id"):
                diagnostic["site_id"] = self.site_id
        
        # Deduplicate: keep only the latest diagnostic for each (device_id, alarm_type) combination
        # Note: diagnostics are linked to alarms via alarm_id, so we deduplicate by (device_id, alarm_type)
        if deduplicate and diagnostics:
            from datetime import datetime
            # Group by (device_id, alarm_type) and keep only the latest one
            diagnostic_groups: Dict[tuple, Dict[str, Any]] = {}
            for diagnostic in diagnostics:
                device_id = diagnostic.get("device_id", "")
                alarm_type_key = diagnostic.get("alarm_type", "")
                
                # Try to extract device_id from alarm_id if not present
                if not device_id:
                    alarm_id = diagnostic.get("alarm_id", "")
                    if alarm_id and "_" in alarm_id:
                        parts = alarm_id.split("_")
                        if len(parts) >= 2:
                            # Try to find device_id in the parts (usually the second part)
                            for part in parts[1:]:  # Skip first part (rule_id)
                                # Check if this part looks like a device_id (contains letters/numbers)
                                if len(part) > 2 and any(c.isalpha() for c in part):
                                    device_id = part
                                    break
                
                # Try to get alarm_type from diagnostic metadata or from alarm_id
                if not alarm_type_key:
                    # Try to extract from alarm_id if it contains type info
                    alarm_id = diagnostic.get("alarm_id", "")
                    if alarm_id and "_" in alarm_id:
                        # Alarm ID format might be: {rule_id}_{device_id}_{timestamp}
                        # For now, use alarm_id as fallback if we can't find alarm_type
                        alarm_type_key = alarm_id
                
                # Use fallback values if missing to ensure diagnostics are not skipped
                if not device_id:
                    device_id = "UNKNOWN"
                if not alarm_type_key:
                    alarm_type_key = "UNKNOWN"
                
                key = (device_id, alarm_type_key)
                
                # Parse timestamp
                timestamp_str = diagnostic.get("timestamp", "")
                try:
                    if isinstance(timestamp_str, str):
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    else:
                        timestamp = timestamp_str
                except Exception:
                    # If timestamp parsing fails, skip this diagnostic
                    continue
                
                # Keep the latest diagnostic for this (device_id, alarm_type) combination
                if key not in diagnostic_groups:
                    diagnostic_groups[key] = diagnostic
                else:
                    existing_timestamp_str = diagnostic_groups[key].get("timestamp", "")
                    try:
                        if isinstance(existing_timestamp_str, str):
                            existing_timestamp = datetime.fromisoformat(existing_timestamp_str.replace("Z", "+00:00"))
                        else:
                            existing_timestamp = existing_timestamp_str
                        if timestamp > existing_timestamp:
                            diagnostic_groups[key] = diagnostic
                    except Exception:
                        # If timestamp comparison fails, keep existing
                        pass
            
            # Convert back to list and sort by timestamp (descending)
            diagnostics = list(diagnostic_groups.values())
            diagnostics.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            # Apply limit
            diagnostics = diagnostics[:limit]
        
        return diagnostics

    def delete_diagnostics(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        risk_level: Optional[str] = None,
        alarm_id: Optional[str] = None,
        device_ids: Optional[List[str]] = None,
    ) -> int:
        """Delete diagnostics from site container"""
        diagnostics = self.query_diagnostics(
            start_time=start_time,
            end_time=end_time,
            risk_level=risk_level,
            alarm_id=alarm_id,
            device_ids=device_ids,
            limit=10000,
        )
        
        if not diagnostics:
            return 0
        
        try:
            delete_api = self.influx_client_base.client.delete_api()
            
            predicate = f'_measurement="diagnostics"'
            if risk_level:
                predicate += f' AND risk_level="{risk_level}"'
            if alarm_id:
                predicate += f' AND alarm_id="{alarm_id}"'
            if device_ids:
                device_filter = " OR ".join([f'device_id="{d}"' for d in device_ids])
                predicate += f' AND ({device_filter})'
            
            from datetime import datetime, timedelta, UTC
            if start_time:
                start = start_time
            else:
                start = datetime.now(UTC) - timedelta(days=30)
            
            if end_time:
                stop = end_time
            else:
                stop = datetime.now(UTC) + timedelta(days=1)
            
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=predicate,
                bucket=self.bucket,
                org=self.influx_client_base.org,
            )
            
            deleted_count = len(diagnostics)
            logger.info(f"Deleted {deleted_count} diagnostics from site {self.site_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to delete diagnostics from site {self.site_id}: {e}", exc_info=True)
            return 0

    # ==================== Device Data Operations ====================
    
    def write_device_data(self, device_data: DeviceData, flush: bool = False):
        """Write device data to site container"""
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
        """Query device time series from site container"""
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
        """Delete device data from site container"""
        try:
            delete_api = self.influx_client_base.client.delete_api()
            
            predicate = f'_measurement="device_data"'
            if device_ids:
                device_filter = " OR ".join([f'device_id="{d}"' for d in device_ids])
                predicate += f' AND ({device_filter})'
            
            from datetime import datetime, timedelta, UTC
            if start_time:
                start = start_time
            else:
                start = datetime.now(UTC) - timedelta(days=30)
            
            if end_time:
                stop = end_time
            else:
                stop = datetime.now(UTC) + timedelta(days=1)
            
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=predicate,
                bucket=self.bucket,
                org=self.influx_client_base.org,
            )
            
            logger.info(f"Deleted device data from site {self.site_id}")
            return 1  # Success
        except Exception as e:
            logger.error(f"Failed to delete device data from site {self.site_id}: {e}", exc_info=True)
            return 0

    def delete_diagnostic(self, alarm_id: str) -> bool:
        """Delete diagnostic report from site container"""
        try:
            return self.influx_client.delete_diagnostic(alarm_id, site_id=self.site_id)
        except Exception as e:
            logger.error(f"Failed to delete diagnostic from site {self.site_id}: {e}", exc_info=True)
            return False

    # ==================== Rules Operations ====================
    
    def write_rule(self, rule: Dict[str, Any], flush: bool = False):
        """Write rule to site container"""
        try:
            from influxdb_client import Point
            import json
            from datetime import datetime, UTC
            
            rule_id = rule.get("id", "unknown")
            
            # Store rule as JSON in InfluxDB
            point = (
                Point("rules")
                .tag("rule_id", rule_id)
                .tag("site_id", self.site_id)
                .field("rule_json", json.dumps(rule))
                .field("exists", 1)
                .time(datetime.now(UTC))
            )
            
            if self.influx_client.use_async:
                self.influx_client._write_buffer.append(point)
                if len(self.influx_client._write_buffer) >= self.influx_client.batch_size or flush:
                    self.influx_client.write_api.write(
                        bucket=self.bucket,
                        org=self.influx_client.org,
                        record=self.influx_client._write_buffer
                    )
                    self.influx_client._write_buffer = []
            else:
                self.influx_client.write_api.write(
                    bucket=self.bucket,
                    org=self.influx_client.org,
                    record=point
                )
            
            logger.debug(f"Wrote rule {rule_id} to site container {self.bucket}")
            return True
        except Exception as e:
            logger.error(f"Failed to write rule to site container: {e}", exc_info=True)
            return False
    
    def flush_rules(self):
        """Flush any pending rule writes to InfluxDB"""
        try:
            if hasattr(self.influx_client, '_write_buffer') and self.influx_client._write_buffer:
                buffer_size = len(self.influx_client._write_buffer)
                self.influx_client.write_api.write(
                    bucket=self.bucket,
                    org=self.influx_client.org,
                    record=self.influx_client._write_buffer
                )
                self.influx_client._write_buffer = []
                logger.debug(f"Flushed {buffer_size} pending rule writes for site {self.site_id}")
        except Exception as e:
            logger.error(f"Failed to flush rules for site {self.site_id}: {e}", exc_info=True)
    
    def query_rules(self, rule_id: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Query rules from site container"""
        try:
            import json
            
            # Build Flux query
            query = f'from(bucket: "{self.bucket}")'
            query += ' |> range(start: -10y)'  # Rules don't expire
            query += ' |> filter(fn: (r) => r["_measurement"] == "rules")'
            query += f' |> filter(fn: (r) => r["site_id"] == "{self.site_id}")'
            query += ' |> filter(fn: (r) => r["_field"] == "rule_json")'  # Only get rule_json field
            
            if rule_id:
                query += f' |> filter(fn: (r) => r["rule_id"] == "{rule_id}")'
            
            # Group by rule_id to get latest value for each rule
            query += ' |> group(columns: ["rule_id"])'
            query += ' |> sort(columns: ["_time"], desc: true)'
            query += ' |> group(columns: ["rule_id"])'
            query += ' |> first()'  # Get latest value for each rule_id
            query += f' |> limit(n: {limit})'
            
            # Execute query
            result = self.influx_client.query_api.query(query=query, org=self.influx_client.org)
            
            rules = []
            seen_rule_ids = set()  # Deduplicate by rule_id (keep latest)
            
            for table in result:
                for record in table.records:
                    rule_id_val = record.values.get("rule_id")
                    if not rule_id_val or rule_id_val in seen_rule_ids:
                        continue
                    seen_rule_ids.add(rule_id_val)
                    
                    # Get rule_json from _value field
                    rule_json = record.get_value()
                    if rule_json:
                        try:
                            if isinstance(rule_json, str):
                                rule = json.loads(rule_json)
                            else:
                                # If already a dict, use it directly
                                rule = rule_json
                            rules.append(rule)
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Failed to parse rule JSON for rule_id {rule_id_val}: {e}")
            
            return rules
        except Exception as e:
            logger.error(f"Failed to query rules from site container: {e}", exc_info=True)
            return []
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete rule from site container"""
        try:
            delete_api = self.influx_client_base.client.delete_api()
            
            predicate = f'_measurement="rules" AND rule_id="{rule_id}" AND site_id="{self.site_id}"'
            
            from datetime import datetime, timedelta, UTC
            start = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=predicate,
                bucket=self.bucket,
                org=self.influx_client_base.org,
            )
            
            logger.info(f"Deleted rule {rule_id} from site {self.site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete rule from site {self.site_id}: {e}", exc_info=True)
            return False
    
    def delete_all_rules(self) -> int:
        """Delete all rules from site container"""
        try:
            delete_api = self.influx_client_base.client.delete_api()
            
            predicate = f'_measurement="rules" AND site_id="{self.site_id}"'
            
            from datetime import datetime, timedelta, UTC
            start = datetime.now(UTC) - timedelta(days=3650)
            stop = datetime.now(UTC) + timedelta(days=1)
            
            delete_api.delete(
                start=start,
                stop=stop,
                predicate=predicate,
                bucket=self.bucket,
                org=self.influx_client_base.org,
            )
            
            logger.info(f"Deleted all rules from site {self.site_id}")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete all rules from site {self.site_id}: {e}", exc_info=True)
            return 0

    # ==================== Container Management ====================
    
    def delete_all_data(self) -> bool:
        """
        Delete all data in site container (delete entire bucket)
        This is the cleanest way to delete a site's data
        """
        try:
            buckets_api = self.influx_client_base.client.buckets_api()
            
            # Find and delete bucket
            buckets = buckets_api.find_buckets()
            # Handle both Buckets object and list
            if hasattr(buckets, 'buckets'):
                bucket_list = buckets.buckets
            elif isinstance(buckets, list):
                bucket_list = buckets
            else:
                bucket_list = list(buckets) if buckets else []
            
            bucket = next((b for b in bucket_list if b.name == self.bucket), None)
            
            if bucket:
                buckets_api.delete_bucket(bucket)
                logger.info(f"✓ Deleted bucket for site {self.site_id}: {self.bucket}")
                return True
            else:
                logger.warning(f"Bucket for site {self.site_id} not found: {self.bucket}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete bucket for site {self.site_id}: {e}", exc_info=True)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for site container"""
        try:
            alarms = self.query_alarms(limit=1)
            diagnostics = self.query_diagnostics(limit=1)
            
            # Get approximate counts (query with large limit)
            alarm_count = len(self.query_alarms(limit=10000))
            diagnostic_count = len(self.query_diagnostics(limit=10000))
            
            return {
                "site_id": self.site_id,
                "bucket": self.bucket,
                "alarm_count": alarm_count,
                "diagnostic_count": diagnostic_count,
                "has_data": alarm_count > 0 or diagnostic_count > 0,
            }
        except Exception as e:
            logger.error(f"Failed to get stats for site {self.site_id}: {e}", exc_info=True)
            return {
                "site_id": self.site_id,
                "bucket": self.bucket,
                "error": str(e),
            }

    def exists(self) -> bool:
        """Check if site container (bucket) exists"""
        try:
            buckets_api = self.influx_client_base.client.buckets_api()
            buckets = buckets_api.find_buckets()
            # Handle both Buckets object and list
            if hasattr(buckets, 'buckets'):
                bucket_list = buckets.buckets
            elif isinstance(buckets, list):
                bucket_list = buckets
            else:
                bucket_list = list(buckets) if buckets else []
            return any(b.name == self.bucket for b in bucket_list)
        except Exception as e:
            logger.error(f"Failed to check bucket existence for site {self.site_id}: {e}")
            return False


class SiteContainerManager:
    """
    Manager for site containers
    Provides unified interface to access site-specific containers
    """

    def __init__(self, influx_client_base: InfluxDBClient):
        """
        Initialize container manager

        Args:
            influx_client_base: Base InfluxDB client
        """
        self.influx_client_base = influx_client_base
        self._containers: Dict[str, SiteContainer] = {}

    def get_container(self, site_id: str, auto_create: bool = True) -> Optional[SiteContainer]:
        """
        Get site container, create if it doesn't exist

        Args:
            site_id: Site ID
            auto_create: Automatically create container if it doesn't exist

        Returns:
            SiteContainer instance or None
        """
        if site_id in self._containers:
            return self._containers[site_id]

        if auto_create:
            container = SiteContainer(site_id, self.influx_client_base, auto_create_bucket=True)
            self._containers[site_id] = container
            return container
        else:
            # Check if container exists
            container = SiteContainer(site_id, self.influx_client_base, auto_create_bucket=False)
            if container.exists():
                self._containers[site_id] = container
                return container
        
        return None

    def delete_container(self, site_id: str) -> bool:
        """
        Delete site container and all its data

        Args:
            site_id: Site ID

        Returns:
            True if successful
        """
        # Remove from cache first
        container = self._containers.pop(site_id, None)
        
        if not container:
            # Try to get container without creating it
            container = self.get_container(site_id, auto_create=False)
        
        if container:
            try:
                # Delete the entire bucket (not just data) to ensure complete cleanup
                buckets_api = self.influx_client_base.client.buckets_api()
                buckets = buckets_api.find_buckets()
                
                # Handle both Buckets object and list
                if hasattr(buckets, 'buckets'):
                    bucket_list = buckets.buckets
                elif isinstance(buckets, list):
                    bucket_list = buckets
                else:
                    bucket_list = list(buckets) if buckets else []
                
                bucket_obj = next((b for b in bucket_list if b.name == container.bucket), None)
                if bucket_obj:
                    buckets_api.delete_bucket(bucket_obj)
                    logger.info(f"✓ Deleted bucket {container.bucket} for site {site_id}")
                    return True
                else:
                    logger.warning(f"Bucket {container.bucket} not found for site {site_id}, may already be deleted")
                    return True  # Consider it successful if bucket doesn't exist
            except Exception as e:
                logger.error(f"Failed to delete bucket for site {site_id}: {e}", exc_info=True)
                # Fallback to deleting data only
                try:
                    success = container.delete_all_data()
                    if success:
                        logger.info(f"✓ Deleted all data from bucket {container.bucket} for site {site_id}")
                    return success
                except Exception as fallback_error:
                    logger.error(f"Failed to delete data from bucket for site {site_id}: {fallback_error}", exc_info=True)
                    return False
        else:
            logger.warning(f"Container for site {site_id} not found, may already be deleted")
            return True  # Consider it successful if container doesn't exist

    def list_containers(self) -> List[str]:
        """List all site containers (buckets)"""
        try:
            buckets_api = self.influx_client_base.client.buckets_api()
            buckets = buckets_api.find_buckets()
            # Handle both Buckets object and list
            if hasattr(buckets, 'buckets'):
                bucket_list = buckets.buckets
            elif isinstance(buckets, list):
                bucket_list = buckets
            else:
                bucket_list = list(buckets) if buckets else []
            
            # Filter buckets that match site_* pattern
            site_buckets = [b.name for b in bucket_list if b.name.startswith("site_")]
            site_ids = [b.replace("site_", "") for b in site_buckets]
            return site_ids
        except Exception as e:
            logger.error(f"Failed to list site containers: {e}", exc_info=True)
            return []

