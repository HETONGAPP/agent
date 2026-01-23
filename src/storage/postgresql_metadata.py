"""
PostgreSQL Metadata Storage
Store sites and devices metadata in PostgreSQL for persistence
"""

import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgreSQLMetadataStorage:
    """Store and retrieve sites and devices metadata from PostgreSQL"""

    def __init__(self, database):
        """
        Initialize metadata storage

        Args:
            database: Database instance from core.database
        """
        self.database = database
        from ..core.database import SiteModel, DeviceModel
        self.SiteModel = SiteModel
        self.DeviceModel = DeviceModel

    @contextmanager
    def _get_session(self):
        """Get database session with automatic cleanup"""
        session = self.database.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def save_site(self, site_data: Dict[str, Any]) -> bool:
        """
        Save site metadata to PostgreSQL

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

            with self._get_session() as session:
                # Check if site exists
                site = session.query(self.SiteModel).filter_by(site_id=site_id).first()
                
                if site:
                    # Update existing site
                    site.site_name = site_data.get("site_name", site.site_name)
                    site.location = site_data.get("location", site.location)
                    site.timezone = site_data.get("timezone", site.timezone or "UTC")
                    site.climate = site_data.get("climate", site.climate)
                    site.country = site_data.get("country", site.country)
                    site.state = site_data.get("state", site.state)
                    site.latitude = site_data.get("latitude", site.latitude)
                    site.longitude = site_data.get("longitude", site.longitude)
                    site.settings = site_data.get("settings", site.settings or {})
                    site.devices_config = site_data.get("devices_config") or site_data.get("devices", site.devices_config or {})
                    site.updated_at = datetime.utcnow()
                    logger.debug(f"Updated site {site_id} in PostgreSQL")
                else:
                    # Create new site
                    site = self.SiteModel(
                        site_id=site_id,
                        site_name=site_data.get("site_name", site_id),
                        location=site_data.get("location", ""),
                        timezone=site_data.get("timezone", "UTC"),
                        climate=site_data.get("climate", ""),
                        country=site_data.get("country", ""),
                        state=site_data.get("state", ""),
                        latitude=site_data.get("latitude"),
                        longitude=site_data.get("longitude"),
                        settings=site_data.get("settings", {}),
                        devices_config=site_data.get("devices_config") or site_data.get("devices", {}),
                    )
                    session.add(site)
                    logger.debug(f"Created site {site_id} in PostgreSQL")

            logger.info(f"Saved site metadata to PostgreSQL: {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save site to PostgreSQL: {e}", exc_info=True)
            return False

    def get_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        """
        Get site metadata from PostgreSQL

        Args:
            site_id: Site ID

        Returns:
            Site data dictionary or None if not found
        """
        try:
            with self._get_session() as session:
                site = session.query(self.SiteModel).filter_by(site_id=site_id).first()
                
                if not site:
                    return None

                return {
                    "site_id": site.site_id,
                    "site_name": site.site_name,
                    "location": site.location,
                    "timezone": site.timezone,
                    "climate": site.climate,
                    "country": site.country,
                    "state": site.state,
                    "latitude": site.latitude,
                    "longitude": site.longitude,
                    "settings": site.settings or {},
                    "devices_config": site.devices_config or {},
                    "created_at": site.created_at.isoformat() if site.created_at else None,
                    "updated_at": site.updated_at.isoformat() if site.updated_at else None,
                }
        except Exception as e:
            logger.error(f"Failed to get site from PostgreSQL: {e}", exc_info=True)
            return None

    def get_all_sites(self) -> List[Dict[str, Any]]:
        """
        Get all sites from PostgreSQL

        Returns:
            List of site data dictionaries
        """
        try:
            with self._get_session() as session:
                sites = session.query(self.SiteModel).all()
                
                return [
                    {
                        "site_id": site.site_id,
                        "site_name": site.site_name,
                        "location": site.location,
                        "timezone": site.timezone,
                        "climate": site.climate,
                        "country": site.country,
                        "state": site.state,
                        "latitude": site.latitude,
                        "longitude": site.longitude,
                        "settings": site.settings or {},
                        "devices_config": site.devices_config or {},
                        "created_at": site.created_at.isoformat() if site.created_at else None,
                        "updated_at": site.updated_at.isoformat() if site.updated_at else None,
                    }
                    for site in sites
                ]
        except Exception as e:
            logger.error(f"Failed to get all sites from PostgreSQL: {e}", exc_info=True)
            return []

    def delete_site(self, site_id: str) -> bool:
        """
        Delete site from PostgreSQL

        Args:
            site_id: Site ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_session() as session:
                site = session.query(self.SiteModel).filter_by(site_id=site_id).first()
                
                if not site:
                    logger.warning(f"Site {site_id} not found in PostgreSQL")
                    return False

                session.delete(site)
                logger.info(f"Deleted site {site_id} from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to delete site from PostgreSQL: {e}", exc_info=True)
            return False

    def save_device(self, device_data: Dict[str, Any]) -> bool:
        """
        Save device metadata to PostgreSQL

        Args:
            device_data: Device configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            device_id = device_data.get("device_id")
            if not device_id:
                logger.error("device_id is required")
                return False

            with self._get_session() as session:
                # Check if device exists
                device = session.query(self.DeviceModel).filter_by(device_id=device_id).first()
                
                if device:
                    # Update existing device
                    device.device_type = device_data.get("device_type", device.device_type)
                    device.integration_name = device_data.get("integration_name", device.integration_name)
                    device.status = device_data.get("status", device.status)
                    device.site_id = device_data.get("site_id", device.site_id)
                    device.device_metadata = device_data.get("metadata", device.device_metadata or {})
                    device.last_seen = datetime.utcnow() if device_data.get("last_seen") else device.last_seen
                    device.updated_at = datetime.utcnow()
                    logger.debug(f"Updated device {device_id} in PostgreSQL")
                else:
                    # Create new device
                    device = self.DeviceModel(
                        device_id=device_id,
                        device_type=device_data.get("device_type", "UNKNOWN"),
                        integration_name=device_data.get("integration_name"),
                        status=device_data.get("status", "registered"),
                        site_id=device_data.get("site_id"),
                        device_metadata=device_data.get("metadata", {}),
                        last_seen=datetime.utcnow() if device_data.get("last_seen") else None,
                    )
                    session.add(device)
                    logger.debug(f"Created device {device_id} in PostgreSQL")

            logger.info(f"Saved device metadata to PostgreSQL: {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save device to PostgreSQL: {e}", exc_info=True)
            return False

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device metadata from PostgreSQL

        Args:
            device_id: Device ID

        Returns:
            Device data dictionary or None if not found
        """
        try:
            with self._get_session() as session:
                device = session.query(self.DeviceModel).filter_by(device_id=device_id).first()
                
                if not device:
                    return None

                return {
                    "device_id": device.device_id,
                    "device_type": device.device_type,
                    "integration_name": device.integration_name,
                    "status": device.status,
                    "site_id": device.site_id,
                    "metadata": device.device_metadata or {},
                    "registered_at": device.registered_at.isoformat() if device.registered_at else None,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "updated_at": device.updated_at.isoformat() if device.updated_at else None,
                }
        except Exception as e:
            logger.error(f"Failed to get device from PostgreSQL: {e}", exc_info=True)
            return None

    def get_devices_by_site(self, site_id: str) -> List[Dict[str, Any]]:
        """
        Get all devices for a site from PostgreSQL

        Args:
            site_id: Site ID

        Returns:
            List of device data dictionaries
        """
        try:
            with self._get_session() as session:
                devices = session.query(self.DeviceModel).filter_by(site_id=site_id).all()
                
                return [
                    {
                        "device_id": device.device_id,
                        "device_type": device.device_type,
                        "integration_name": device.integration_name,
                        "status": device.status,
                        "site_id": device.site_id,
                        "metadata": device.device_metadata or {},
                        "registered_at": device.registered_at.isoformat() if device.registered_at else None,
                        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                        "updated_at": device.updated_at.isoformat() if device.updated_at else None,
                    }
                    for device in devices
                ]
        except Exception as e:
            logger.error(f"Failed to get devices for site {site_id} from PostgreSQL: {e}", exc_info=True)
            return []

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices from PostgreSQL

        Returns:
            List of device data dictionaries
        """
        try:
            with self._get_session() as session:
                devices = session.query(self.DeviceModel).all()
                
                return [
                    {
                        "device_id": device.device_id,
                        "device_type": device.device_type,
                        "integration_name": device.integration_name,
                        "status": device.status,
                        "site_id": device.site_id,
                        "metadata": device.device_metadata or {},
                        "registered_at": device.registered_at.isoformat() if device.registered_at else None,
                        "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                        "updated_at": device.updated_at.isoformat() if device.updated_at else None,
                    }
                    for device in devices
                ]
        except Exception as e:
            logger.error(f"Failed to get all devices from PostgreSQL: {e}", exc_info=True)
            return []

    def delete_device(self, device_id: str) -> bool:
        """
        Delete device from PostgreSQL

        Args:
            device_id: Device ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_session() as session:
                device = session.query(self.DeviceModel).filter_by(device_id=device_id).first()
                
                if not device:
                    logger.warning(f"Device {device_id} not found in PostgreSQL")
                    return False

                session.delete(device)
                logger.info(f"Deleted device {device_id} from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to delete device from PostgreSQL: {e}", exc_info=True)
            return False

