"""
InfluxDB Metadata Storage
Store sites and devices metadata in InfluxDB for persistence
"""

import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from influxdb_client import Point

logger = logging.getLogger(__name__)


class InfluxDBMetadataStorage:
    """Store and retrieve sites and devices metadata from InfluxDB"""

    def __init__(self, influx_client):
        """
        Initialize metadata storage

        Args:
            influx_client: InfluxDBClient instance
        """
        self.influx_client = influx_client
        self.sites_measurement = "sites_metadata"
        self.devices_measurement = "devices_metadata"
    
    def _get_bucket_for_site(self, site_id: str) -> str:
        """
        Get bucket name for a site
        Uses site-specific bucket if site containers are enabled, otherwise uses default bucket
        
        Args:
            site_id: Site ID
            
        Returns:
            Bucket name
        """
        # Check if site containers are enabled by checking if bucket name pattern matches
        # If default bucket is "alarms" and it doesn't exist, use site bucket
        default_bucket = self.influx_client.bucket
        if default_bucket == "alarms":
            # Site container mode: use site-specific bucket
            return f"site_{site_id}"
        # Legacy mode: use default bucket
        return default_bucket
    
    def _get_bucket_for_device(self, device_data: Dict[str, Any]) -> str:
        """
        Get bucket name for a device based on its site_id
        
        Args:
            device_data: Device data dictionary
            
        Returns:
            Bucket name
        """
        site_id = device_data.get("site_id")
        if not site_id and "metadata" in device_data:
            site_id = device_data.get("metadata", {}).get("site_id")
        
        if site_id:
            return self._get_bucket_for_site(site_id)
        
        # Fallback to default bucket
        return self.influx_client.bucket
    
    def _ensure_bucket_exists(self, bucket_name: str) -> bool:
        """
        Ensure bucket exists, create if it doesn't
        
        Args:
            bucket_name: Bucket name to check/create
            
        Returns:
            True if bucket exists or was created successfully, False otherwise
        """
        try:
            buckets_api = self.influx_client.client.buckets_api()
            
            # Check if bucket exists
            try:
                buckets = buckets_api.find_buckets()
                if hasattr(buckets, 'buckets'):
                    bucket_list = buckets.buckets
                elif isinstance(buckets, list):
                    bucket_list = buckets
                else:
                    bucket_list = list(buckets) if buckets else []
                
                bucket_exists = any(b.name == bucket_name for b in bucket_list)
            except Exception:
                bucket_exists = False
            
            if bucket_exists:
                return True
            
            # Create bucket if it doesn't exist
            # Get org ID from org name
            orgs_api = self.influx_client.client.organizations_api()
            orgs = orgs_api.find_organizations()
            org_id = None
            if hasattr(orgs, 'orgs'):
                org_list = orgs.orgs
            elif isinstance(orgs, list):
                org_list = orgs
            else:
                org_list = list(orgs) if orgs else []
            
            for org in org_list:
                if org.name == self.influx_client.org:
                    org_id = org.id
                    break
            
            if not org_id:
                # Fallback: try to create with org name
                org_id = self.influx_client.org
            
            # Create bucket with default retention policy (30 days)
            from influxdb_client.domain.bucket import Bucket
            from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules
            
            # 30 days retention
            retention_seconds = 30 * 24 * 60 * 60
            retention_rules = BucketRetentionRules(type="expire", every_seconds=retention_seconds)
            bucket = Bucket(
                name=bucket_name,
                org_id=org_id,
                retention_rules=[retention_rules],
            )
            buckets_api.create_bucket(bucket=bucket)
            logger.info(f"✓ Created bucket: {bucket_name} (retention: 30 days)")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure bucket {bucket_name} exists: {e}", exc_info=True)
            return False

    def save_site(self, site_data: Dict[str, Any]) -> bool:
        """
        Save site metadata to InfluxDB

        Args:
            site_data: Site configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            site_id = site_data.get("site_id")
            if not site_id:
                logger.error("site_id is required")
                return False

            # Create point with site_id as tag and all other data as fields
            # Use explicit UTC time for consistency
            now = datetime.now(UTC)
            point = (
                Point(self.sites_measurement)
                .tag("site_id", site_id)
                .field("exists", True)  # Marker field
                .time(now)
            )

            # Add string fields
            if "site_name" in site_data:
                point = point.field("site_name", str(site_data["site_name"]))
            if "location" in site_data:
                point = point.field("location", str(site_data.get("location", "")))
            if "timezone" in site_data:
                point = point.field("timezone", str(site_data.get("timezone", "UTC")))
            if "climate" in site_data:
                point = point.field("climate", str(site_data.get("climate", "")))
            if "country" in site_data:
                point = point.field("country", str(site_data.get("country", "")))
            if "state" in site_data:
                point = point.field("state", str(site_data.get("state", "")))

            # Add numeric fields
            if "latitude" in site_data and site_data["latitude"] is not None:
                point = point.field("latitude", float(site_data["latitude"]))
            if "longitude" in site_data and site_data["longitude"] is not None:
                point = point.field("longitude", float(site_data["longitude"]))

            # Store complex data as JSON string in a field
            import json
            if "settings" in site_data:
                point = point.field("settings_json", json.dumps(site_data.get("settings", {})))
            if "devices" in site_data or "devices_config" in site_data:
                devices_config = site_data.get("devices") or site_data.get("devices_config", {})
                point = point.field("devices_json", json.dumps(devices_config))

            # Write to InfluxDB - use site-specific bucket
            bucket_name = self._get_bucket_for_site(site_id)
            
            # Ensure bucket exists before writing
            if not self._ensure_bucket_exists(bucket_name):
                logger.error(f"Failed to create bucket {bucket_name} for site {site_id}")
                return False
            
            try:
                self.influx_client.write_api.write(
                    bucket=bucket_name,
                    org=self.influx_client.org,
                    record=point
                )
            except Exception as write_error:
                logger.error(f"Failed to write to bucket {bucket_name}: {write_error}")
                return False

            logger.debug(f"Saved site metadata to InfluxDB: {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save site to InfluxDB: {e}", exc_info=True)
            return False

    def get_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        """
        Get site metadata from InfluxDB (excluding deleted sites)

        Args:
            site_id: Site ID

        Returns:
            Site configuration dictionary or None if not found or deleted
        """
        try:
            # Use site-specific bucket
            bucket_name = self._get_bucket_for_site(site_id)
            # First check if site is marked as deleted
            exists_query = f'''
            from(bucket: "{bucket_name}")
              |> range(start: -10y)
              |> filter(fn: (r) => r["_measurement"] == "{self.sites_measurement}")
              |> filter(fn: (r) => r["site_id"] == "{site_id}")
              |> filter(fn: (r) => r["_field"] == "exists")
              |> sort(columns: ["_time"], desc: true)
              |> first()
            '''
            
            try:
                exists_result = self.influx_client.query_api.query(
                    org=self.influx_client.org,
                    query=exists_query
                )
            except Exception as query_error:
                # If bucket doesn't exist (404), site doesn't exist
                error_str = str(query_error)
                if "not found" in error_str.lower() or "404" in error_str:
                    logger.debug(f"Bucket {bucket_name} does not exist, site {site_id} not found")
                    return None
                raise
            
            # Check if site is marked as deleted
            has_exists_record = False
            exists_value = None
            for table in exists_result:
                for record in table.records:
                    has_exists_record = True
                    exists_value = record.get_value()
                    if exists_value is False:
                        logger.debug(f"Site {site_id} is marked as deleted")
                        return None
            
            # If exists record exists and is True, proceed to get site data
            # If no exists record exists, also proceed (for backward compatibility)
            # But if exists record is False, we already returned None above
            
            # Query latest record for this site_id (excluding exists field)
            query = f'''
            from(bucket: "{bucket_name}")
              |> range(start: -10y)
              |> filter(fn: (r) => r["_measurement"] == "{self.sites_measurement}")
              |> filter(fn: (r) => r["site_id"] == "{site_id}")
              |> filter(fn: (r) => r["_field"] != "exists")
              |> last()
            '''

            try:
                result = self.influx_client.query_api.query(
                    org=self.influx_client.org,
                    query=query
                )
            except Exception as query_error:
                # If bucket doesn't exist (404), site doesn't exist
                error_str = str(query_error)
                if "not found" in error_str.lower() or "404" in error_str:
                    logger.debug(f"Bucket {bucket_name} does not exist, site {site_id} not found")
                    return None
                raise

            if not result or len(result) == 0:
                # No data found at all
                return None
            
            # If we have exists record and it's True, or no exists record at all, return data
            # But if exists record is False, we should have returned None already
            # Double-check: if exists record exists and is not True, return None
            if has_exists_record and exists_value is not True:
                logger.debug(f"Site {site_id} exists record is not True: {exists_value}")
                return None

            # Convert result to dictionary
            site_data = {"site_id": site_id}
            import json

            for table in result:
                for record in table.records:
                    field_name = record.get_field()
                    field_value = record.get_value()

                    if field_name == "site_name":
                        site_data["site_name"] = field_value
                    elif field_name == "location":
                        site_data["location"] = field_value
                    elif field_name == "timezone":
                        site_data["timezone"] = field_value
                    elif field_name == "climate":
                        site_data["climate"] = field_value
                    elif field_name == "country":
                        site_data["country"] = field_value
                    elif field_name == "state":
                        site_data["state"] = field_value
                    elif field_name == "latitude":
                        site_data["latitude"] = field_value
                    elif field_name == "longitude":
                        site_data["longitude"] = field_value
                    elif field_name == "settings_json":
                        try:
                            site_data["settings"] = json.loads(field_value)
                        except:
                            pass
                    elif field_name == "devices_json":
                        try:
                            site_data["devices"] = json.loads(field_value)
                            site_data["devices_config"] = site_data["devices"]
                        except:
                            pass

            return site_data if len(site_data) > 1 else None  # More than just site_id
        except Exception as e:
            logger.error(f"Failed to get site from InfluxDB: {e}", exc_info=True)
            return None

    def get_all_sites(self) -> List[Dict[str, Any]]:
        """
        Get all sites from InfluxDB (excluding deleted sites)
        In site container mode, queries all site buckets

        Returns:
            List of site configuration dictionaries
        """
        try:
            # In site container mode, we need to query all site buckets
            # First, try to list all site buckets
            try:
                buckets_api = self.influx_client.client.buckets_api()
                buckets = buckets_api.find_buckets()
                if hasattr(buckets, 'buckets'):
                    bucket_list = buckets.buckets
                elif isinstance(buckets, list):
                    bucket_list = buckets
                else:
                    bucket_list = list(buckets) if buckets else []
                
                # Filter buckets that match site_* pattern
                site_buckets = [b.name for b in bucket_list if b.name.startswith("site_")]
                site_ids = [b.replace("site_", "") for b in site_buckets]
                
                # Get full data for each site
                sites = []
                for site_id in site_ids:
                    site_data = self.get_site(site_id)
                    if site_data:
                        sites.append(site_data)
                
                return sites
            except Exception as e:
                logger.warning(f"Failed to list site buckets, trying fallback: {e}")
                # Fallback: try to query from default bucket (legacy mode)
                query = f'''
                from(bucket: "{self.influx_client.bucket}")
                  |> range(start: -10y)
                  |> filter(fn: (r) => r["_measurement"] == "{self.sites_measurement}")
                  |> filter(fn: (r) => r["_field"] == "exists")
                  |> group(columns: ["site_id"])
                  |> sort(columns: ["_time"], desc: true)
                  |> first()
                  |> filter(fn: (r) => r["_value"] == true)
                '''

                result = self.influx_client.query_api.query(
                    org=self.influx_client.org,
                    query=query
                )

                site_ids = set()
                for table in result:
                    for record in table.records:
                        site_id = record.values.get("site_id")
                        if site_id:
                            site_ids.add(site_id)

                # Get full data for each site
                sites = []
                for site_id in site_ids:
                    site_data = self.get_site(site_id)
                    if site_data:
                        sites.append(site_data)

                return sites
        except Exception as e:
            logger.error(f"Failed to get all sites from InfluxDB: {e}", exc_info=True)
            return []

    def delete_site(self, site_id: str) -> bool:
        """
        Delete site metadata from InfluxDB
        This permanently deletes all site metadata records using delete API

        Args:
            site_id: Site ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use delete API to permanently remove all site metadata
            delete_api = self.influx_client.client.delete_api()
            
            from datetime import datetime, timedelta, UTC
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            # Delete all site metadata records for this site_id
            predicate = f'_measurement="{self.sites_measurement}" AND site_id="{site_id}"'
            bucket_name = self._get_bucket_for_site(site_id)
            
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=predicate,
                    bucket=bucket_name,
                    org=self.influx_client.org
                )
                logger.info(f"✓ Permanently deleted all site metadata from InfluxDB: {site_id}")
            except Exception as delete_error:
                # If bucket doesn't exist (404), consider it already deleted
                error_str = str(delete_error)
                if "not found" in error_str.lower() or "404" in error_str:
                    logger.debug(f"Bucket {bucket_name} does not exist, site {site_id} already deleted")
                    return True
                # Re-raise other errors
                raise

            return True
        except Exception as e:
            logger.error(f"Failed to delete site from InfluxDB: {e}", exc_info=True)
            return False

    def save_device(self, device_data: Dict[str, Any]) -> bool:
        """
        Save device metadata to InfluxDB

        Args:
            device_data: Device information dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            device_id = device_data.get("device_id")
            if not device_id:
                logger.error("device_id is required")
                return False

            # Create point with device_id as tag
            # Use explicit UTC time to ensure consistent timestamps
            now = datetime.now(UTC)
            point = (
                Point(self.devices_measurement)
                .tag("device_id", device_id)
                .field("exists", True)  # Marker field - always write exists=True when saving
                .time(now)  # Use explicit UTC time
            )

            # Add fields
            if "device_type" in device_data:
                point = point.tag("device_type", str(device_data["device_type"]))
            if "integration_name" in device_data:
                point = point.tag("integration_name", str(device_data["integration_name"]))
            if "status" in device_data:
                point = point.tag("status", str(device_data["status"]))
            
            # Extract site_id from metadata if not in top level
            site_id = device_data.get("site_id")
            if not site_id and "metadata" in device_data:
                metadata = device_data.get("metadata", {})
                site_id = metadata.get("site_id")
            if site_id:
                point = point.tag("site_id", str(site_id))

            # Store metadata as JSON
            import json
            if "metadata" in device_data:
                point = point.field("metadata_json", json.dumps(device_data.get("metadata", {})))

            # Add timestamps
            if "registered_at" in device_data:
                try:
                    if isinstance(device_data["registered_at"], str):
                        reg_time = datetime.fromisoformat(device_data["registered_at"].replace("Z", "+00:00"))
                    else:
                        reg_time = device_data["registered_at"]
                    point = point.field("registered_at", reg_time.isoformat())
                except:
                    pass

            if "last_seen" in device_data and device_data["last_seen"]:
                try:
                    if isinstance(device_data["last_seen"], str):
                        seen_time = datetime.fromisoformat(device_data["last_seen"].replace("Z", "+00:00"))
                    else:
                        seen_time = device_data["last_seen"]
                    point = point.field("last_seen", seen_time.isoformat())
                except:
                    pass

            # Write to InfluxDB - use site-specific bucket if available
            bucket_name = self._get_bucket_for_device(device_data)
            
            # Ensure bucket exists before writing
            if not self._ensure_bucket_exists(bucket_name):
                logger.error(f"Failed to create bucket {bucket_name} for device {device_id}")
                return False
            
            try:
                self.influx_client.write_api.write(
                    bucket=bucket_name,
                    org=self.influx_client.org,
                    record=point
                )
            except Exception as write_error:
                logger.error(f"Failed to write to bucket {bucket_name}: {write_error}")
                return False

            logger.debug(f"Saved device metadata to InfluxDB: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save device to InfluxDB: {e}", exc_info=True)
            return False

    def get_device(self, device_id: str, site_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get device metadata from InfluxDB

        Args:
            device_id: Device ID
            site_id: Optional site ID to specify which bucket to query

        Returns:
            Device information dictionary or None if not found or deleted
        """
        try:
            # Try to find device in site bucket if site_id is provided
            # Otherwise, try all site buckets
            if site_id:
                buckets_to_try = [self._get_bucket_for_site(site_id)]
            else:
                # Try to find device in all site buckets
                try:
                    buckets_api = self.influx_client.client.buckets_api()
                    buckets = buckets_api.find_buckets()
                    if hasattr(buckets, 'buckets'):
                        bucket_list = buckets.buckets
                    elif isinstance(buckets, list):
                        bucket_list = buckets
                    else:
                        bucket_list = list(buckets) if buckets else []
                    buckets_to_try = [b.name for b in bucket_list if b.name.startswith("site_")]
                except:
                    buckets_to_try = [self.influx_client.bucket]
            
            # Try each bucket
            for bucket_name in buckets_to_try:
                try:
                    # First check if device exists (not deleted)
                    exists_query = f'''
                    from(bucket: "{bucket_name}")
                      |> range(start: -10y)
                      |> filter(fn: (r) => r["_measurement"] == "{self.devices_measurement}")
                      |> filter(fn: (r) => r["device_id"] == "{device_id}")
                      |> filter(fn: (r) => r["_field"] == "exists")
                      |> group(columns: ["device_id"])
                      |> sort(columns: ["_time"], desc: true)
                      |> limit(n: 1)
                    '''
            
                    exists_result = self.influx_client.query_api.query(
                        org=self.influx_client.org,
                        query=exists_query
                    )
                    
                    # Check if device exists (exists field should be True in the latest record)
                    device_exists = None  # None means no exists record found
                    for table in exists_result:
                        for record in table.records:
                            exists_value = record.get_value()
                            if exists_value is True:
                                device_exists = True
                                break
                            elif exists_value is False:
                                device_exists = False
                                break
                    
                    # If device doesn't exist in this bucket, try next
                    if device_exists is not True:
                        continue
                    
                    # Query device metadata fields (excluding exists field)
                    query = f'''
                    from(bucket: "{bucket_name}")
                      |> range(start: -10y)
                      |> filter(fn: (r) => r["_measurement"] == "{self.devices_measurement}")
                      |> filter(fn: (r) => r["device_id"] == "{device_id}")
                      |> filter(fn: (r) => r["_field"] != "exists")
                      |> group(columns: ["device_id", "_field"])
                      |> sort(columns: ["_time"], desc: true)
                      |> group(columns: ["device_id", "_field"])
                      |> first()
                    '''

                    result = self.influx_client.query_api.query(
                        org=self.influx_client.org,
                        query=query
                    )

                    if not result or len(result) == 0:
                        continue

                    device_data = {"device_id": device_id}
                    import json

                    for table in result:
                        for record in table.records:
                            # Get tags
                            site_id_tag = record.values.get("site_id")
                            if site_id_tag:
                                device_data["site_id"] = site_id_tag
                            device_type = record.values.get("device_type")
                            if device_type:
                                device_data["device_type"] = device_type
                            integration_name = record.values.get("integration_name")
                            if integration_name:
                                device_data["integration_name"] = integration_name
                            status = record.values.get("status")
                            if status:
                                device_data["status"] = status

                            # Get fields
                            field_name = record.get_field()
                            field_value = record.get_value()

                            if field_name == "metadata_json":
                                try:
                                    device_data["metadata"] = json.loads(field_value)
                                except:
                                    device_data["metadata"] = {}
                            elif field_name == "registered_at":
                                device_data["registered_at"] = field_value
                            elif field_name == "last_seen":
                                device_data["last_seen"] = field_value

                    return device_data if len(device_data) > 1 else None
                except Exception as e:
                    logger.debug(f"Failed to query device from bucket {bucket_name}: {e}")
                    continue
            
            # Device not found in any bucket
            return None
        except Exception as e:
            logger.error(f"Failed to get device from InfluxDB: {e}", exc_info=True)
            return None

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices from InfluxDB (excluding deleted devices)
        In site container mode, queries all site buckets

        Returns:
            List of device information dictionaries
        """
        try:
            # In site container mode, query all site buckets
            try:
                buckets_api = self.influx_client.client.buckets_api()
                buckets = buckets_api.find_buckets()
                if hasattr(buckets, 'buckets'):
                    bucket_list = buckets.buckets
                elif isinstance(buckets, list):
                    bucket_list = buckets
                else:
                    bucket_list = list(buckets) if buckets else []
                
                # Filter buckets that match site_* pattern
                site_buckets = [b.name for b in bucket_list if b.name.startswith("site_")]
                
                device_ids = set()
                # Query each site bucket
                for bucket_name in site_buckets:
                    try:
                        query_device_ids = f'''
                        from(bucket: "{bucket_name}")
                          |> range(start: -10y)
                          |> filter(fn: (r) => r["_measurement"] == "{self.devices_measurement}")
                          |> filter(fn: (r) => r["_field"] == "exists")
                          |> filter(fn: (r) => r["_value"] == true)
                          |> group(columns: ["device_id"])
                          |> distinct(column: "device_id")
                        '''

                        result = self.influx_client.query_api.query(
                            org=self.influx_client.org,
                            query=query_device_ids
                        )

                        for table in result:
                            for record in table.records:
                                device_id = record.values.get("device_id")
                                if device_id:
                                    device_ids.add(device_id)
                    except Exception as e:
                        logger.debug(f"Failed to query devices from bucket {bucket_name}: {e}")
                        continue
                
                # Get full data for each device
                devices = []
                for device_id in device_ids:
                    device_data = self.get_device(device_id)
                    if device_data:
                        devices.append(device_data)

                return devices
            except Exception as e:
                logger.warning(f"Failed to list site buckets, trying fallback: {e}")
                # Fallback: try to query from default bucket (legacy mode)
                query_device_ids = f'''
                from(bucket: "{self.influx_client.bucket}")
                  |> range(start: -10y)
                  |> filter(fn: (r) => r["_measurement"] == "{self.devices_measurement}")
                  |> filter(fn: (r) => r["_field"] == "exists")
                  |> group(columns: ["device_id"])
                  |> distinct(column: "device_id")
                '''

                result = self.influx_client.query_api.query(
                    org=self.influx_client.org,
                    query=query_device_ids
                )

                device_ids = set()
                for table in result:
                    for record in table.records:
                        device_id = record.values.get("device_id")
                        if device_id:
                            device_ids.add(device_id)

                # Get full data for each device
                devices = []
                for device_id in device_ids:
                    device_data = self.get_device(device_id)
                    if device_data:
                        devices.append(device_data)

                return devices
        except Exception as e:
            logger.error(f"Failed to get all devices from InfluxDB: {e}", exc_info=True)
            return []

    def delete_device(self, device_id: str, site_id: Optional[str] = None) -> bool:
        """
        Delete device metadata from InfluxDB
        This permanently deletes all device metadata records using delete API

        Args:
            device_id: Device ID to delete
            site_id: Optional site ID to specify which bucket to delete from.
                    If not provided, will try to determine from device data.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use delete API to permanently remove all device metadata
            delete_api = self.influx_client.client.delete_api()
            
            from datetime import datetime, timedelta, UTC
            # Delete from last 10 years to future (covers all data)
            start_time = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago
            stop_time = datetime.now(UTC) + timedelta(days=1)  # Tomorrow
            
            # Determine bucket name
            bucket_name = None
            if site_id:
                # Use provided site_id to determine bucket
                bucket_name = self._get_bucket_for_site(site_id)
            else:
                # Try to find device first to determine which bucket to delete from
                device_data = self.get_device(device_id)
                if device_data:
                    device_site_id = device_data.get("site_id")
                    if device_site_id:
                        bucket_name = self._get_bucket_for_site(device_site_id)
                    else:
                        bucket_name = self.influx_client.bucket
                else:
                    # Device not found, try default bucket
                    bucket_name = self.influx_client.bucket
            
            predicate = f'_measurement="{self.devices_measurement}" AND device_id="{device_id}"'
            
            try:
                delete_api.delete(
                    start=start_time,
                    stop=stop_time,
                    predicate=predicate,
                    bucket=bucket_name,
                    org=self.influx_client.org
                )
                logger.info(f"✓ Permanently deleted all device metadata from InfluxDB: {device_id} (bucket: {bucket_name})")
            except Exception as delete_error:
                error_str = str(delete_error)
                if "not found" in error_str.lower() or "404" in error_str:
                    logger.debug(f"Bucket {bucket_name} does not exist or device {device_id} already deleted, considering it successful.")
                    return True
                raise  # Re-raise other errors

            return True
        except Exception as e:
            logger.error(f"Failed to delete device from InfluxDB: {e}", exc_info=True)
            return False



