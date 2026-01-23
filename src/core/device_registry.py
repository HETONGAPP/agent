"""
Device Registry
Stores and manages registered devices with InfluxDB persistence
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from ..models.device_data import DeviceType

logger = logging.getLogger(__name__)


class DeviceStatus(str, Enum):
    """Device status"""

    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNREGISTERED = "unregistered"


@dataclass
class RegisteredDevice:
    """Registered device information"""

    device_id: str
    device_type: DeviceType
    integration_name: str  # Name of the integration (e.g., "bms", "pcs")
    status: DeviceStatus = DeviceStatus.REGISTERED
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def update_last_seen(self):
        """Update last seen timestamp"""
        self.last_seen = datetime.now(timezone.utc)
        if self.status == DeviceStatus.REGISTERED:
            self.status = DeviceStatus.ACTIVE

    def mark_inactive(self):
        """Mark device as inactive"""
        self.status = DeviceStatus.INACTIVE

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "integration_name": self.integration_name,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": self.metadata,
        }


class DeviceRegistry:
    """Device registry for managing registered devices with PostgreSQL (primary) and InfluxDB (secondary) persistence"""

    def __init__(self, influx_metadata_storage=None, postgres_metadata_storage=None):
        """
        Initialize device registry

        Args:
            influx_metadata_storage: Optional InfluxDBMetadataStorage instance for persistence (secondary)
            postgres_metadata_storage: Optional PostgreSQLMetadataStorage instance for persistence (primary)
        """
        self._devices: Dict[str, RegisteredDevice] = {}  # device_id -> RegisteredDevice
        self._devices_by_type: Dict[
            DeviceType, Set[str]
        ] = {}  # device_type -> Set[device_id]
        self._devices_by_integration: Dict[
            str, Set[str]
        ] = {}  # integration_name -> Set[device_id]
        self._postgres_storage = postgres_metadata_storage  # Primary storage
        self._influx_storage = influx_metadata_storage  # Secondary storage
        
        # Load devices from PostgreSQL first, then InfluxDB as fallback
        if self._postgres_storage:
            self._load_from_postgresql()
        elif self._influx_storage:
            self._load_from_influxdb()

    def register_device(
        self,
        device_id: str,
        device_type: DeviceType,
        integration_name: str,
        metadata: Optional[Dict] = None,
    ) -> RegisteredDevice:
        """
        Register a new device

        Args:
            device_id: Device ID
            device_type: Device type
            integration_name: Integration name
            metadata: Optional metadata

        Returns:
            Registered device object
        """
        # Check if device already exists in memory
        if device_id in self._devices:
            existing_device = self._devices[device_id]
            # If device is UNREGISTERED (deleted), allow re-registration
            if existing_device.status == DeviceStatus.UNREGISTERED:
                # Remove from memory to allow re-registration
                del self._devices[device_id]
                # Safely remove from indexes (check if keys exist)
                if existing_device.device_type in self._devices_by_type:
                    self._devices_by_type[existing_device.device_type].discard(device_id)
                integration_key = existing_device.integration_name if existing_device.integration_name else "unknown"
                if integration_key in self._devices_by_integration:
                    self._devices_by_integration[integration_key].discard(device_id)
                # Continue to create new device below
            else:
                # Check if device belongs to a different site
                # Allow same device_id to exist in different sites
                existing_site_id = existing_device.metadata.get("site_id") if existing_device.metadata else None
                new_site_id = metadata.get("site_id") if metadata else None
                
                # If both have site_id and they're different, allow registration (will update metadata)
                # This allows the same device_id to be used in different sites
                if new_site_id and existing_site_id and new_site_id != existing_site_id:
                    logger.info(f"Device {device_id} exists in site {existing_site_id}, updating for site {new_site_id}")
                    # Update existing device's metadata to reflect the new site
                    existing_device.update_last_seen()
                    if metadata:
                        existing_device.metadata.update(metadata)
                    return existing_device
                elif new_site_id and existing_site_id and new_site_id == existing_site_id:
                    # Same device_id in same site - update existing device
                    existing_device.update_last_seen()
                    if metadata:
                        existing_device.metadata.update(metadata)
                    return existing_device
                else:
                    # Update existing device (no site_id conflict or no site_id provided)
                    existing_device.update_last_seen()
                    if metadata:
                        existing_device.metadata.update(metadata)
                    return existing_device

        # Check if device was deleted (check PostgreSQL first, then InfluxDB)
        # IMPORTANT: Do NOT allow auto-re-registration of deleted devices
        # Only allow manual re-registration from frontend
        storage_to_check = self._postgres_storage or self._influx_storage
        if storage_to_check:
            try:
                # Check PostgreSQL first (primary)
                deleted_device_data = None
                if self._postgres_storage:
                    deleted_device_data = self._postgres_storage.get_device(device_id)
                # Fallback to InfluxDB
                if deleted_device_data is None and self._influx_storage:
                    deleted_device_data = self._influx_storage.get_device(device_id)
                
                if deleted_device_data is None:
                    # Device was deleted, check if this is a manual registration
                    # Manual registrations have metadata["source"] == "manual" or metadata["registered_via"] == "frontend"
                    is_manual_registration = (
                        metadata and (
                            metadata.get("source") == "manual" or 
                            metadata.get("registered_via") == "frontend"
                        )
                    )
                    if not is_manual_registration:
                        # This is an auto-discovery attempt, reject it
                        logger.warning(f"⛔ Blocking auto-registration of deleted device {device_id}. Use frontend to manually re-register if needed.")
                        # Return a dummy device with UNREGISTERED status to indicate rejection
                        return RegisteredDevice(
                            device_id=device_id,
                            device_type=device_type,
                            integration_name=integration_name,
                            metadata=metadata or {},
                            status=DeviceStatus.UNREGISTERED,
                        )
                    else:
                        # Manual registration from frontend, allow re-registration
                        logger.info(f"✓ Allowing manual re-registration of previously deleted device {device_id}")
            except Exception as e:
                logger.debug(f"Error checking if device {device_id} was deleted: {e}")

        # Create new device
        device = RegisteredDevice(
            device_id=device_id,
            device_type=device_type,
            integration_name=integration_name,
            metadata=metadata or {},
        )

        self._devices[device_id] = device

        # Update indexes
        if device_type not in self._devices_by_type:
            self._devices_by_type[device_type] = set()
        self._devices_by_type[device_type].add(device_id)

        # Handle empty integration_name
        integration_key = integration_name if integration_name else "unknown"
        if integration_key not in self._devices_by_integration:
            self._devices_by_integration[integration_key] = set()
        self._devices_by_integration[integration_key].add(device_id)

        # Persist to PostgreSQL (primary storage)
        if self._postgres_storage:
            try:
                device_dict = device.to_dict()
                # Add site_id from metadata if available
                if device.metadata and "site_id" in device.metadata:
                    device_dict["site_id"] = device.metadata["site_id"]
                self._postgres_storage.save_device(device_dict)
            except Exception as e:
                logger.warning(f"Failed to save device to PostgreSQL: {e} (non-fatal)")

        # Also persist to InfluxDB (secondary storage)
        if self._influx_storage:
            device_dict = device.to_dict()
            self._influx_storage.save_device(device_dict)

        return device

    def unregister_device(self, device_id: str) -> bool:
        """
        Unregister a device
        Removes device from memory cache and marks as deleted in InfluxDB

        Args:
            device_id: Device ID

        Returns:
            True if device was unregistered, False if not found
        """
        device = None
        
        # Remove from memory cache if exists
        if device_id in self._devices:
            device = self._devices[device_id]
            device.status = DeviceStatus.UNREGISTERED

            # Remove from indexes (safely check if keys exist)
            if device.device_type in self._devices_by_type:
                self._devices_by_type[device.device_type].discard(device_id)
            integration_key = device.integration_name if device.integration_name else "unknown"
            if integration_key in self._devices_by_integration:
                self._devices_by_integration[integration_key].discard(device_id)

            # Remove from registry memory cache
            del self._devices[device_id]
            logger.debug(f"Removed device {device_id} from memory cache")

        # Always mark as deleted in PostgreSQL (primary) and InfluxDB (secondary)
        # This ensures the device record is marked as deleted in persistent storage
        db_success = False
        if self._postgres_storage:
            db_success = self._postgres_storage.delete_device(device_id)
            if db_success:
                logger.info(f"Deleted device {device_id} from PostgreSQL")
        
        if self._influx_storage:
            influx_success = self._influx_storage.delete_device(device_id)
            if influx_success:
                logger.debug(f"Marked device {device_id} as deleted in InfluxDB")
            else:
                logger.warning(f"Failed to mark device {device_id} as deleted in InfluxDB")
        
        # Return True if device was in memory or if we successfully marked it as deleted in InfluxDB
        return device is not None or db_success

    def get_device(self, device_id: str) -> Optional[RegisteredDevice]:
        """Get device by ID"""
        # Check memory first
        if device_id in self._devices:
            device = self._devices[device_id]
            # Skip UNREGISTERED devices
            if device.status == DeviceStatus.UNREGISTERED:
                return None
            return device
        
        # If not in memory, check PostgreSQL (primary) or InfluxDB (fallback)
        storage_to_check = self._postgres_storage or self._influx_storage
        if storage_to_check:
            device_data = None
            # Try PostgreSQL first
            if self._postgres_storage:
                try:
                    device_data = self._postgres_storage.get_device(device_id)
                except Exception as e:
                    logger.debug(f"Error loading device {device_id} from PostgreSQL: {e}")
            # Fallback to InfluxDB
            if device_data is None and self._influx_storage:
                try:
                    device_data = self._influx_storage.get_device(device_id)
                except Exception as e:
                    logger.debug(f"Error loading device {device_id} from InfluxDB: {e}")
                    device_data = None
            
            if device_data:
                # Device exists in storage and is not deleted
                # Load it into memory
                device_type_str = device_data.get("device_type")
                integration_name = device_data.get("integration_name", "unknown")
                metadata = device_data.get("metadata", {})
                
                if device_type_str:
                    try:
                        device_type = DeviceType(device_type_str)
                        device = RegisteredDevice(
                            device_id=device_id,
                            device_type=device_type,
                            integration_name=integration_name,
                            metadata=metadata,
                        )
                        # Parse timestamps
                        if device_data.get("registered_at"):
                            try:
                                if isinstance(device_data["registered_at"], str):
                                    device.registered_at = datetime.fromisoformat(
                                        device_data["registered_at"].replace("Z", "+00:00")
                                    )
                                else:
                                    device.registered_at = device_data["registered_at"]
                            except:
                                pass
                        if device_data.get("last_seen"):
                            try:
                                if isinstance(device_data["last_seen"], str):
                                    device.last_seen = datetime.fromisoformat(
                                        device_data["last_seen"].replace("Z", "+00:00")
                                    )
                                else:
                                    device.last_seen = device_data["last_seen"]
                            except:
                                pass
                        # Parse status
                        status_str = device_data.get("status", "registered")
                        try:
                            device.status = DeviceStatus(status_str)
                        except ValueError:
                            device.status = DeviceStatus.REGISTERED
                        
                        # Add to memory
                        self._devices[device_id] = device
                        if device_type not in self._devices_by_type:
                            self._devices_by_type[device_type] = set()
                        self._devices_by_type[device_type].add(device_id)
                        if integration_name not in self._devices_by_integration:
                            self._devices_by_integration[integration_name] = set()
                        self._devices_by_integration[integration_name].add(device_id)
                        
                        return device
                    except ValueError:
                        pass
        
        return None

    def get_devices_by_type(self, device_type: DeviceType) -> List[RegisteredDevice]:
        """Get all devices of a specific type"""
        device_ids = self._devices_by_type.get(device_type, set())
        return [
            self._devices[device_id]
            for device_id in device_ids
            if device_id in self._devices
        ]

    def get_devices_by_integration(
        self, integration_name: str
    ) -> List[RegisteredDevice]:
        """Get all devices for a specific integration"""
        device_ids = self._devices_by_integration.get(integration_name, set())
        return [
            self._devices[device_id]
            for device_id in device_ids
            if device_id in self._devices
        ]

    def get_all_devices(self) -> List[RegisteredDevice]:
        """
        Get all registered devices
        Filters out deleted devices by checking PostgreSQL (primary) or InfluxDB (fallback)
        """
        # Filter out devices that are marked as deleted
        valid_devices = []
        for device_id, device in self._devices.items():
            # Skip UNREGISTERED devices (already deleted in memory)
            if device.status == DeviceStatus.UNREGISTERED:
                continue
            
            # Double-check with PostgreSQL (primary) or InfluxDB (fallback) to ensure device is not deleted
            storage_to_check = self._postgres_storage or self._influx_storage
            if storage_to_check:
                try:
                    device_data = None
                    # Check PostgreSQL first
                    if self._postgres_storage:
                        device_data = self._postgres_storage.get_device(device_id)
                    # Fallback to InfluxDB
                    if device_data is None and self._influx_storage:
                        device_data = self._influx_storage.get_device(device_id)
                    
                    if device_data is None:
                        # Device was deleted, remove from memory
                        logger.debug(f"Removing deleted device from memory: {device_id}")
                        # Remove from memory cache
                        if device_id in self._devices:
                            del self._devices[device_id]
                        if device.device_type in self._devices_by_type:
                            self._devices_by_type[device.device_type].discard(device_id)
                        integration_key = device.integration_name if device.integration_name else "unknown"
                        if integration_key in self._devices_by_integration:
                            self._devices_by_integration[integration_key].discard(device_id)
                        continue
                except Exception as e:
                    logger.debug(f"Error checking device {device_id} in storage: {e}")
                    # If check fails, include device to avoid false negatives
                    pass
            
            valid_devices.append(device)
        
        return valid_devices

    def get_new_devices(self, since: datetime) -> List[RegisteredDevice]:
        """
        Get devices registered after a specific time

        Args:
            since: Timestamp to compare against

        Returns:
            List of newly registered devices
        """
        return [
            device for device in self._devices.values() if device.registered_at > since
        ]

    def update_device_status(self, device_id: str, status: DeviceStatus):
        """Update device status"""
        device = self.get_device(device_id)
        if device:
            device.status = status
            # Persist to PostgreSQL (primary)
            if self._postgres_storage:
                try:
                    device_dict = device.to_dict()
                    if device.metadata and "site_id" in device.metadata:
                        device_dict["site_id"] = device.metadata["site_id"]
                    self._postgres_storage.save_device(device_dict)
                except Exception as e:
                    logger.warning(f"Failed to update device status in PostgreSQL: {e} (non-fatal)")
            # Also persist to InfluxDB (secondary)
            if self._influx_storage:
                device_dict = device.to_dict()
                self._influx_storage.save_device(device_dict)
            return True
        return False

    def update_device(
        self,
        device_id: str,
        integration_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[RegisteredDevice]:
        """
        Update device information (integration_name and/or metadata)
        
        Args:
            device_id: Device ID
            integration_name: Optional new integration name
            metadata: Optional metadata dict (will be merged with existing metadata)
        
        Returns:
            Updated device object, or None if device not found
        """
        device = self.get_device(device_id)
        if not device:
            return None
        
        # Update integration_name if provided
        if integration_name is not None:
            # Update index if integration_name changed
            old_integration_key = device.integration_name if device.integration_name else "unknown"
            new_integration_key = integration_name if integration_name else "unknown"
            
            if old_integration_key != new_integration_key:
                # Remove from old index
                if old_integration_key in self._devices_by_integration:
                    self._devices_by_integration[old_integration_key].discard(device_id)
                # Add to new index
                if new_integration_key not in self._devices_by_integration:
                    self._devices_by_integration[new_integration_key] = set()
                self._devices_by_integration[new_integration_key].add(device_id)
            
            device.integration_name = integration_name
        
        # Update metadata if provided (merge with existing)
        if metadata:
            device.metadata.update(metadata)
        
        # Persist to InfluxDB
        if self._influx_storage:
            device_dict = device.to_dict()
            self._influx_storage.save_device(device_dict)
        
        return device

    def mark_device_seen(self, device_id: str):
        """Mark device as seen (update last_seen)"""
        if device_id in self._devices:
            self._devices[device_id].update_last_seen()
            # Persist to InfluxDB
            if self._influx_storage:
                device_dict = self._devices[device_id].to_dict()
                self._influx_storage.save_device(device_dict)

    def get_inactive_devices(
        self, timeout_seconds: int = 300
    ) -> List[RegisteredDevice]:
        """
        Get devices that haven't been seen for a while

        Args:
            timeout_seconds: Seconds since last_seen to consider inactive

        Returns:
            List of inactive devices
        """
        now = datetime.now(timezone.utc)
        inactive = []

        for device in self._devices.values():
            if device.last_seen:
                # Ensure both datetimes are timezone-aware for comparison
                last_seen = device.last_seen
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                delta = (now - last_seen).total_seconds()
                if delta > timeout_seconds:
                    inactive.append(device)
            elif device.status == DeviceStatus.REGISTERED:
                # Never seen, but registered
                registered_at = device.registered_at
                if registered_at.tzinfo is None:
                    registered_at = registered_at.replace(tzinfo=timezone.utc)
                delta = (now - registered_at).total_seconds()
                if delta > timeout_seconds:
                    inactive.append(device)

        return inactive

    def _load_from_postgresql(self):
        """Load all devices from PostgreSQL on initialization"""
        if not self._postgres_storage:
            return

        try:
            devices_data = self._postgres_storage.get_all_devices()
            for device_data in devices_data:
                try:
                    # Skip if status is unregistered
                    if device_data.get("status") == "unregistered":
                        continue

                    device_id = device_data.get("device_id")
                    device_type_str = device_data.get("device_type")
                    integration_name = device_data.get("integration_name", "unknown")
                    metadata = device_data.get("metadata", {})

                    if not device_id or not device_type_str:
                        continue

                    # Convert device_type string to enum
                    try:
                        device_type = DeviceType(device_type_str)
                    except ValueError:
                        continue

                    # Parse timestamps
                    from datetime import UTC
                    registered_at = datetime.now(UTC)
                    if device_data.get("registered_at"):
                        try:
                            if isinstance(device_data["registered_at"], str):
                                registered_at = datetime.fromisoformat(
                                    device_data["registered_at"].replace("Z", "+00:00")
                                )
                            else:
                                registered_at = device_data["registered_at"]
                        except:
                            pass

                    last_seen = None
                    if device_data.get("last_seen"):
                        try:
                            if isinstance(device_data["last_seen"], str):
                                last_seen = datetime.fromisoformat(
                                    device_data["last_seen"].replace("Z", "+00:00")
                                )
                            else:
                                last_seen = device_data["last_seen"]
                        except:
                            pass

                    # Create device object
                    status_str = device_data.get("status", "registered")
                    try:
                        status = DeviceStatus(status_str)
                    except ValueError:
                        status = DeviceStatus.REGISTERED

                    device = RegisteredDevice(
                        device_id=device_id,
                        device_type=device_type,
                        integration_name=integration_name,
                        status=status,
                        registered_at=registered_at,
                        last_seen=last_seen,
                        metadata=metadata,
                    )

                    # Add to registry
                    self._devices[device_id] = device

                    # Update indexes
                    if device_type not in self._devices_by_type:
                        self._devices_by_type[device_type] = set()
                    self._devices_by_type[device_type].add(device_id)

                    if integration_name not in self._devices_by_integration:
                        self._devices_by_integration[integration_name] = set()
                    self._devices_by_integration[integration_name].add(device_id)

                except Exception as e:
                    logger.warning(f"Failed to load device {device_data.get('device_id')}: {e}")

            logger.info(f"Loaded {len(self._devices)} devices from PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to load devices from PostgreSQL: {e}", exc_info=True)
            # Fallback to InfluxDB
            if self._influx_storage:
                logger.info("Falling back to InfluxDB for device loading")
                self._load_from_influxdb()

    def _load_from_influxdb(self):
        """Load all devices from InfluxDB on initialization"""
        if not self._influx_storage:
            return

        try:
            # get_all_devices() already filters out deleted devices (exists=False)
            # So we can safely load all returned devices
            devices_data = self._influx_storage.get_all_devices()
            for device_data in devices_data:
                try:
                    # get_all_devices() already checks exists field, so we don't need to check again
                    # But we can still skip if status is explicitly unregistered (extra safety)
                    if device_data.get("status") == "unregistered":
                        continue

                    device_id = device_data.get("device_id")
                    device_type_str = device_data.get("device_type")
                    integration_name = device_data.get("integration_name", "unknown")
                    metadata = device_data.get("metadata", {})

                    if not device_id or not device_type_str:
                        continue

                    # Convert device_type string to enum
                    try:
                        device_type = DeviceType(device_type_str)
                    except ValueError:
                        continue

                    # Parse timestamps
                    from datetime import UTC
                    registered_at = datetime.now(UTC)
                    if device_data.get("registered_at"):
                        try:
                            if isinstance(device_data["registered_at"], str):
                                registered_at = datetime.fromisoformat(
                                    device_data["registered_at"].replace("Z", "+00:00")
                                )
                            else:
                                registered_at = device_data["registered_at"]
                        except:
                            pass

                    last_seen = None
                    if device_data.get("last_seen"):
                        try:
                            if isinstance(device_data["last_seen"], str):
                                last_seen = datetime.fromisoformat(
                                    device_data["last_seen"].replace("Z", "+00:00")
                                )
                            else:
                                last_seen = device_data["last_seen"]
                        except:
                            pass

                    # Create device object
                    status_str = device_data.get("status", "registered")
                    try:
                        status = DeviceStatus(status_str)
                    except ValueError:
                        status = DeviceStatus.REGISTERED

                    device = RegisteredDevice(
                        device_id=device_id,
                        device_type=device_type,
                        integration_name=integration_name,
                        status=status,
                        registered_at=registered_at,
                        last_seen=last_seen,
                        metadata=metadata,
                    )

                    # Add to registry
                    self._devices[device_id] = device

                    # Update indexes
                    if device_type not in self._devices_by_type:
                        self._devices_by_type[device_type] = set()
                    self._devices_by_type[device_type].add(device_id)

                    if integration_name not in self._devices_by_integration:
                        self._devices_by_integration[integration_name] = set()
                    self._devices_by_integration[integration_name].add(device_id)

                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to load device {device_data.get('device_id')}: {e}")

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to load devices from InfluxDB: {e}", exc_info=True)
