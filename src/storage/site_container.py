"""
Site Container - Containerized data management per site
Each site has its own isolated data container (InfluxDB bucket)
Provides clean data isolation, easy deletion, and independent management
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .influxdb_client import InfluxDBClient
from .site_alarm_container import SiteAlarmMixin
from .site_diagnostic_container import SiteDiagnosticMixin
from .site_device_container import SiteDeviceMixin

logger = logging.getLogger(__name__)


def delete_site_bucket(influx_client: Optional[InfluxDBClient], site_id: str) -> bool:
    """
    Delete InfluxDB bucket for a site by name (site_{site_id}).
    Used when container_manager is not available (e.g. during delete_site).
    Returns True if bucket was deleted or did not exist.
    """
    if influx_client is None:
        return False
    bucket_name = f"site_{site_id}"
    try:
        buckets_api = influx_client.client.buckets_api()
        buckets = buckets_api.find_buckets()
        if hasattr(buckets, "buckets"):
            bucket_list = buckets.buckets
        elif isinstance(buckets, list):
            bucket_list = buckets
        else:
            bucket_list = list(buckets) if buckets else []
        bucket_obj = next((b for b in bucket_list if b.name == bucket_name), None)
        if bucket_obj:
            buckets_api.delete_bucket(bucket_obj)
            logger.info(f"✓ Deleted bucket {bucket_name} for site {site_id}")
            return True
        logger.debug(f"Bucket {bucket_name} for site {site_id} not found, already deleted")
        return True
    except Exception as e:
        logger.error(f"Failed to delete bucket {bucket_name} for site {site_id}: {e}", exc_info=True)
        return False


class SiteContainer(SiteAlarmMixin, SiteDiagnosticMixin, SiteDeviceMixin):
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

