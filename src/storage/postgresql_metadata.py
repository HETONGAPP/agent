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
        from ..core.database import SiteModel, DeviceModel, RuleModel, DiagnosticModel
        self.SiteModel = SiteModel
        self.DeviceModel = DeviceModel
        self.RuleModel = RuleModel
        self.DiagnosticModel = DiagnosticModel

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

    def save_rule(self, site_id: str, rule_data: Dict[str, Any]) -> bool:
        """
        Save rule to PostgreSQL

        Args:
            site_id: Site ID
            rule_data: Rule configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            rule_id = rule_data.get("id") or rule_data.get("rule_id")
            if not rule_id:
                logger.error("rule_id is required")
                return False

            with self._get_session() as session:
                # Check if rule exists
                rule = session.query(self.RuleModel).filter_by(
                    rule_id=rule_id,
                    site_id=site_id
                ).first()
                
                if rule:
                    # Update existing rule
                    rule.name = rule_data.get("name", rule.name)
                    rule.description = rule_data.get("description", rule.description)
                    rule.device_types = rule_data.get("device_types", rule.device_types or [])
                    rule.device_ids = rule_data.get("device_ids", rule.device_ids or [])
                    rule.condition = rule_data.get("condition", rule.condition)
                    rule.severity = rule_data.get("severity", rule.severity)
                    rule.priority = rule_data.get("priority", rule.priority or 0)
                    rule.actions = rule_data.get("actions", rule.actions or [])
                    rule.rule_metadata = rule_data.get("metadata", rule.rule_metadata or {})
                    rule.enabled = rule_data.get("enabled", rule.enabled if rule.enabled is not None else True)
                    rule.updated_at = datetime.utcnow()
                    logger.debug(f"Updated rule {rule_id} for site {site_id} in PostgreSQL")
                else:
                    # Create new rule
                    rule = self.RuleModel(
                        rule_id=rule_id,
                        site_id=site_id,
                        name=rule_data.get("name", ""),
                        description=rule_data.get("description"),
                        device_types=rule_data.get("device_types", []),
                        device_ids=rule_data.get("device_ids", []),
                        condition=rule_data.get("condition", {}),
                        severity=rule_data.get("severity"),
                        priority=rule_data.get("priority", 0),
                        actions=rule_data.get("actions", []),
                        rule_metadata=rule_data.get("metadata", {}),
                        enabled=rule_data.get("enabled", True),
                    )
                    session.add(rule)
                    logger.debug(f"Created rule {rule_id} for site {site_id} in PostgreSQL")

            logger.info(f"Saved rule {rule_id} for site {site_id} to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Failed to save rule to PostgreSQL: {e}", exc_info=True)
            return False

    def get_rule(self, site_id: str, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        Get rule from PostgreSQL

        Args:
            site_id: Site ID
            rule_id: Rule ID

        Returns:
            Rule data dictionary or None if not found
        """
        try:
            with self._get_session() as session:
                rule = session.query(self.RuleModel).filter_by(
                    rule_id=rule_id,
                    site_id=site_id
                ).first()
                
                if not rule:
                    return None

                return {
                    "id": rule.rule_id,
                    "rule_id": rule.rule_id,
                    "site_id": rule.site_id,
                    "name": rule.name,
                    "description": rule.description,
                    "device_types": rule.device_types or [],
                    "device_ids": rule.device_ids or [],
                    "condition": rule.condition or {},
                    "severity": rule.severity,
                    "priority": rule.priority or 0,
                    "actions": rule.actions or [],
                    "metadata": rule.rule_metadata or {},
                    "enabled": rule.enabled if rule.enabled is not None else True,
                    "created_at": rule.created_at.isoformat() if rule.created_at else None,
                    "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
                    "created_by": rule.created_by,
                    "updated_by": rule.updated_by,
                }
        except Exception as e:
            logger.error(f"Failed to get rule from PostgreSQL: {e}", exc_info=True)
            return None

    def get_rules_by_site(self, site_id: str, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all rules for a site from PostgreSQL

        Args:
            site_id: Site ID
            enabled_only: If True, only return enabled rules

        Returns:
            List of rule data dictionaries
        """
        try:
            with self._get_session() as session:
                query = session.query(self.RuleModel).filter_by(site_id=site_id)
                if enabled_only:
                    query = query.filter_by(enabled=True)
                rules = query.order_by(self.RuleModel.priority.desc()).all()
                
                return [
                    {
                        "id": rule.rule_id,
                        "rule_id": rule.rule_id,
                        "site_id": rule.site_id,
                        "name": rule.name,
                        "description": rule.description,
                        "device_types": rule.device_types or [],
                        "device_ids": rule.device_ids or [],
                        "condition": rule.condition or {},
                        "severity": rule.severity,
                        "priority": rule.priority or 0,
                        "actions": rule.actions or [],
                        "metadata": rule.rule_metadata or {},
                        "enabled": rule.enabled if rule.enabled is not None else True,
                        "created_at": rule.created_at.isoformat() if rule.created_at else None,
                        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
                        "created_by": rule.created_by,
                        "updated_by": rule.updated_by,
                    }
                    for rule in rules
                ]
        except Exception as e:
            logger.error(f"Failed to get rules for site {site_id} from PostgreSQL: {e}", exc_info=True)
            return []

    def delete_rule(self, site_id: str, rule_id: str) -> bool:
        """
        Delete rule from PostgreSQL

        Args:
            site_id: Site ID
            rule_id: Rule ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_session() as session:
                rule = session.query(self.RuleModel).filter_by(
                    rule_id=rule_id,
                    site_id=site_id
                ).first()
                
                if not rule:
                    logger.warning(f"Rule {rule_id} not found for site {site_id} in PostgreSQL")
                    return False

                session.delete(rule)
                logger.info(f"Deleted rule {rule_id} for site {site_id} from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to delete rule from PostgreSQL: {e}", exc_info=True)
            return False

    def get_rules_by_device_type(self, site_id: str, device_type: str, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get rules for a specific device type from PostgreSQL

        Args:
            site_id: Site ID
            device_type: Device type (e.g., "BMS", "PCS")
            enabled_only: If True, only return enabled rules

        Returns:
            List of rule data dictionaries
        """
        try:
            with self._get_session() as session:
                from sqlalchemy import func
                # Query rules where device_types JSON array contains the device_type
                query = session.query(self.RuleModel).filter_by(site_id=site_id)
                if enabled_only:
                    query = query.filter_by(enabled=True)
                
                # Get all rules for the site
                rules = query.all()
                
                # Filter in Python (PostgreSQL JSONB contains is complex, so filter in Python)
                result = []
                for rule in rules:
                    device_types = rule.device_types or []
                    # Check if device_type is in the array, or if it's an EMS rule (matches all)
                    if device_type in device_types or "EMS" in device_types:
                        result.append({
                            "id": rule.rule_id,
                            "rule_id": rule.rule_id,
                            "site_id": rule.site_id,
                            "name": rule.name,
                            "description": rule.description,
                            "device_types": device_types,
                            "device_ids": rule.device_ids or [],
                            "condition": rule.condition or {},
                            "severity": rule.severity,
                            "priority": rule.priority or 0,
                            "actions": rule.actions or [],
                            "metadata": rule.rule_metadata or {},
                            "enabled": rule.enabled if rule.enabled is not None else True,
                            "created_at": rule.created_at.isoformat() if rule.created_at else None,
                            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
                        })
                
                # Sort by priority
                result.sort(key=lambda x: x.get("priority", 0), reverse=True)
                return result
        except Exception as e:
            logger.error(f"Failed to get rules by device type from PostgreSQL: {e}", exc_info=True)
            return []

    def save_diagnostic(self, diagnostic_data: Dict[str, Any]) -> bool:
        """
        Save diagnostic metadata to PostgreSQL

        Args:
            diagnostic_data: Diagnostic metadata dictionary with keys:
                - alarm_id: Required, primary key
                - site_id: Optional
                - device_id: Optional
                - device_type: Optional
                - alarm_type: Optional
                - risk_level: Required (High, Medium, Low)
                - current_status: Optional
                - diagnostic_name: Optional
                - generated_at: Optional datetime or ISO string
                - metadata: Optional additional metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            alarm_id = diagnostic_data.get("alarm_id")
            if not alarm_id:
                logger.error("alarm_id is required for diagnostic")
                return False

            risk_level = diagnostic_data.get("risk_level")
            if not risk_level:
                logger.error("risk_level is required for diagnostic")
                return False

            with self._get_session() as session:
                # Check if diagnostic exists
                diagnostic = session.query(self.DiagnosticModel).filter_by(alarm_id=alarm_id).first()
                
                # Parse generated_at if provided
                generated_at = diagnostic_data.get("generated_at")
                if generated_at:
                    if isinstance(generated_at, str):
                        from dateutil.parser import parse
                        generated_at = parse(generated_at)
                    elif not isinstance(generated_at, datetime):
                        generated_at = datetime.utcnow()
                else:
                    generated_at = datetime.utcnow()
                
                if diagnostic:
                    # Update existing diagnostic
                    diagnostic.site_id = diagnostic_data.get("site_id", diagnostic.site_id)
                    diagnostic.device_id = diagnostic_data.get("device_id", diagnostic.device_id)
                    diagnostic.device_type = diagnostic_data.get("device_type", diagnostic.device_type)
                    diagnostic.alarm_type = diagnostic_data.get("alarm_type", diagnostic.alarm_type)
                    diagnostic.risk_level = risk_level
                    diagnostic.current_status = diagnostic_data.get("current_status", diagnostic.current_status)
                    diagnostic.diagnostic_name = diagnostic_data.get("diagnostic_name", diagnostic.diagnostic_name)
                    diagnostic.generated_at = generated_at
                    diagnostic.diagnostic_metadata = diagnostic_data.get("metadata", diagnostic.diagnostic_metadata)
                    diagnostic.updated_at = datetime.utcnow()
                    logger.debug(f"Updated diagnostic {alarm_id} in PostgreSQL")
                else:
                    # Create new diagnostic
                    diagnostic = self.DiagnosticModel(
                        alarm_id=alarm_id,
                        site_id=diagnostic_data.get("site_id"),
                        device_id=diagnostic_data.get("device_id"),
                        device_type=diagnostic_data.get("device_type"),
                        alarm_type=diagnostic_data.get("alarm_type"),
                        risk_level=risk_level,
                        current_status=diagnostic_data.get("current_status"),
                        diagnostic_name=diagnostic_data.get("diagnostic_name"),
                        generated_at=generated_at,
                        diagnostic_metadata=diagnostic_data.get("metadata"),
                    )
                    session.add(diagnostic)
                    logger.debug(f"Created diagnostic {alarm_id} in PostgreSQL")

            logger.info(f"Saved diagnostic metadata to PostgreSQL: {alarm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save diagnostic to PostgreSQL: {e}", exc_info=True)
            return False

    def get_diagnostic(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """
        Get diagnostic metadata by alarm_id

        Args:
            alarm_id: Alarm ID

        Returns:
            Diagnostic metadata dictionary or None
        """
        try:
            with self._get_session() as session:
                diagnostic = session.query(self.DiagnosticModel).filter_by(alarm_id=alarm_id).first()
                if not diagnostic:
                    return None

                return {
                    "alarm_id": diagnostic.alarm_id,
                    "site_id": diagnostic.site_id,
                    "device_id": diagnostic.device_id,
                    "device_type": diagnostic.device_type,
                    "alarm_type": diagnostic.alarm_type,
                    "risk_level": diagnostic.risk_level,
                    "current_status": diagnostic.current_status,
                    "diagnostic_name": diagnostic.diagnostic_name,
                    "generated_at": diagnostic.generated_at.isoformat() if diagnostic.generated_at else None,
                    "created_at": diagnostic.created_at.isoformat() if diagnostic.created_at else None,
                    "updated_at": diagnostic.updated_at.isoformat() if diagnostic.updated_at else None,
                    "metadata": diagnostic.diagnostic_metadata or {},
                }
        except Exception as e:
            logger.error(f"Failed to get diagnostic from PostgreSQL: {e}", exc_info=True)
            return None

    def get_all_diagnostics(
        self,
        site_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all diagnostics with optional filters

        Args:
            site_id: Optional site ID filter
            risk_level: Optional risk level filter (High, Medium, Low)
            limit: Optional limit
            offset: Optional offset

        Returns:
            List of diagnostic metadata dictionaries
        """
        try:
            with self._get_session() as session:
                query = session.query(self.DiagnosticModel)
                
                if site_id:
                    query = query.filter_by(site_id=site_id)
                if risk_level:
                    query = query.filter_by(risk_level=risk_level)
                
                # Order by generated_at descending (newest first)
                query = query.order_by(self.DiagnosticModel.generated_at.desc())
                
                if limit:
                    query = query.limit(limit)
                if offset:
                    query = query.offset(offset)
                
                diagnostics = query.all()
                
                result = []
                for diagnostic in diagnostics:
                    result.append({
                        "alarm_id": diagnostic.alarm_id,
                        "site_id": diagnostic.site_id,
                        "device_id": diagnostic.device_id,
                        "device_type": diagnostic.device_type,
                        "alarm_type": diagnostic.alarm_type,
                        "risk_level": diagnostic.risk_level,
                        "current_status": diagnostic.current_status,
                        "diagnostic_name": diagnostic.diagnostic_name,
                        "generated_at": diagnostic.generated_at.isoformat() if diagnostic.generated_at else None,
                        "created_at": diagnostic.created_at.isoformat() if diagnostic.created_at else None,
                        "updated_at": diagnostic.updated_at.isoformat() if diagnostic.updated_at else None,
                        "metadata": diagnostic.diagnostic_metadata or {},
                    })
                
                return result
        except Exception as e:
            logger.error(f"Failed to get diagnostics from PostgreSQL: {e}", exc_info=True)
            return []

    def delete_diagnostic(self, alarm_id: str) -> bool:
        """
        Delete diagnostic metadata by alarm_id

        Args:
            alarm_id: Alarm ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_session() as session:
                diagnostic = session.query(self.DiagnosticModel).filter_by(alarm_id=alarm_id).first()
                if not diagnostic:
                    logger.warning(f"Diagnostic {alarm_id} not found in PostgreSQL")
                    return False

                session.delete(diagnostic)
                logger.info(f"Deleted diagnostic {alarm_id} from PostgreSQL")
                return True
        except Exception as e:
            logger.error(f"Failed to delete diagnostic from PostgreSQL: {e}", exc_info=True)
            return False

    def delete_diagnostics_by_site(self, site_id: str) -> int:
        """
        Delete all diagnostic metadata for a specific site

        Args:
            site_id: Site ID

        Returns:
            Number of diagnostics deleted
        """
        try:
            with self._get_session() as session:
                diagnostics = session.query(self.DiagnosticModel).filter_by(site_id=site_id).all()
                count = len(diagnostics)
                if count > 0:
                    for diagnostic in diagnostics:
                        session.delete(diagnostic)
                    logger.info(f"Deleted {count} diagnostic(s) for site {site_id} from PostgreSQL")
                else:
                    logger.debug(f"No diagnostics found for site {site_id} in PostgreSQL")
                return count
        except Exception as e:
            logger.error(f"Failed to delete diagnostics for site {site_id} from PostgreSQL: {e}", exc_info=True)
            return 0
