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

            # Write to InfluxDB
            self.influx_client.write_api.write(
                bucket=self.influx_client.bucket,
                org=self.influx_client.org,
                record=point
            )

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
            # First check if site is marked as deleted
            exists_query = f'''
            from(bucket: "{self.influx_client.bucket}")
              |> range(start: -10y)
              |> filter(fn: (r) => r["_measurement"] == "{self.sites_measurement}")
              |> filter(fn: (r) => r["site_id"] == "{site_id}")
              |> filter(fn: (r) => r["_field"] == "exists")
              |> sort(columns: ["_time"], desc: true)
              |> first()
            '''
            
            exists_result = self.influx_client.query_api.query(
                org=self.influx_client.org,
                query=exists_query
            )
            
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
            from(bucket: "{self.influx_client.bucket}")
              |> range(start: -10y)
              |> filter(fn: (r) => r["_measurement"] == "{self.sites_measurement}")
              |> filter(fn: (r) => r["site_id"] == "{site_id}")
              |> filter(fn: (r) => r["_field"] != "exists")
              |> last()
            '''

            result = self.influx_client.query_api.query(
                org=self.influx_client.org,
                query=query
            )

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

        Returns:
            List of site configuration dictionaries
        """
        try:
            # Query all unique site_ids with their latest exists status
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
            
            delete_api.delete(
                start=start_time,
                stop=stop_time,
                predicate=predicate,
                bucket=self.influx_client.bucket,
                org=self.influx_client.org
            )

            logger.info(f"✓ Permanently deleted all site metadata from InfluxDB: {site_id}")
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

            # Write to InfluxDB
            self.influx_client.write_api.write(
                bucket=self.influx_client.bucket,
                org=self.influx_client.org,
                record=point
            )

            logger.debug(f"Saved device metadata to InfluxDB: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save device to InfluxDB: {e}", exc_info=True)
            return False

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device metadata from InfluxDB

        Args:
            device_id: Device ID

        Returns:
            Device information dictionary or None if not found or deleted
        """
        try:
            # First check if device exists (not deleted)
            # Use group() and last() to ensure we get the latest exists record for this device_id
            exists_query = f'''
            from(bucket: "{self.influx_client.bucket}")
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
            # Since we use last(), we only get the most recent exists record
            device_exists = None  # None means no exists record found
            for table in exists_result:
                for record in table.records:
                    exists_value = record.get_value()
                    # Check if the latest exists record is True
                    # If exists=False is the latest, device was deleted
                    if exists_value is True:
                        device_exists = True
                        break
                    elif exists_value is False:
                        # Latest record shows exists=False, device was deleted
                        device_exists = False
                        break
            
            # If device_exists is False (explicitly deleted) or None (no exists record), return None
            # Only return device if device_exists is explicitly True
            if device_exists is not True:
                # Device doesn't exist, was deleted, or has no exists record (old data)
                return None
            
            # Query device metadata fields (excluding exists field)
            # Get the latest value for each field by grouping and sorting
            query = f'''
            from(bucket: "{self.influx_client.bucket}")
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
                return None

            device_data = {"device_id": device_id}
            import json

            for table in result:
                for record in table.records:
                    # Get tags
                    site_id = record.values.get("site_id")
                    if site_id:
                        device_data["site_id"] = site_id
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
            logger.error(f"Failed to get device from InfluxDB: {e}", exc_info=True)
            return None

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices from InfluxDB (excluding deleted devices)

        Returns:
            List of device information dictionaries
        """
        try:
            # Query all unique device_ids first
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

            # Get full data for each device (get_device will check latest exists value)
            devices = []
            for device_id in device_ids:
                device_data = self.get_device(device_id)
                if device_data:
                    # Only add if device exists (exists=True in latest record)
                    devices.append(device_data)

            return devices
        except Exception as e:
            logger.error(f"Failed to get all devices from InfluxDB: {e}", exc_info=True)
            return []

    def delete_device(self, device_id: str) -> bool:
        """
        Delete device metadata from InfluxDB
        This permanently deletes all device metadata records using delete API

        Args:
            device_id: Device ID to delete

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
            
            # Delete all device metadata records for this device_id
            predicate = f'_measurement="{self.devices_measurement}" AND device_id="{device_id}"'
            
            delete_api.delete(
                start=start_time,
                stop=stop_time,
                predicate=predicate,
                bucket=self.influx_client.bucket,
                org=self.influx_client.org
            )

            logger.info(f"✓ Permanently deleted all device metadata from InfluxDB: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete device from InfluxDB: {e}", exc_info=True)
            return False



