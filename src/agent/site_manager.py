"""
Site Manager
Manages site configurations and provides site-related operations
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import yaml

from .site_rule_manager import SiteRuleManager

logger = logging.getLogger(__name__)


class SiteManager:
    """Manages site configurations and operations with PostgreSQL (primary) and InfluxDB (secondary) persistence"""

    def __init__(self, site_rules_dir: Optional[str] = None, influx_metadata_storage=None, postgres_metadata_storage=None, container_manager=None):
        """
        Initialize site manager

        Args:
            site_rules_dir: Directory containing site configuration files (for backward compatibility)
            influx_metadata_storage: Optional InfluxDBMetadataStorage instance for persistence (secondary)
            postgres_metadata_storage: Optional PostgreSQLMetadataStorage instance for persistence (primary)
            container_manager: Optional SiteContainerManager instance for rule storage in containers
        """
        self.site_rules_dir = Path(site_rules_dir) if site_rules_dir else None
        self._site_configs_cache: Dict[str, Dict[str, Any]] = {}
        self._postgres_storage = postgres_metadata_storage  # Primary storage
        self._influx_storage = influx_metadata_storage  # Secondary storage (for backward compatibility)
        self._container_manager = container_manager
        self._site_rule_manager = SiteRuleManager(
            site_rules_dir=self.site_rules_dir,
            postgres_storage=self._postgres_storage,
            influx_storage=self._influx_storage,
            container_manager=self._container_manager,
            site_exists=self.site_exists,
        )

    def set_container_manager(self, container_manager) -> None:
        """Inject or update container manager so both SiteManager and SiteRuleManager use it."""
        self._container_manager = container_manager
        self._site_rule_manager._container_manager = container_manager

    def get_all_sites(self) -> List[Dict[str, Any]]:
        """
        Get all sites from PostgreSQL (preferred), InfluxDB (fallback), or configuration files

        Returns:
            List of site information dictionaries
        """
        # Try PostgreSQL first (primary storage)
        if self._postgres_storage:
            try:
                sites = self._postgres_storage.get_all_sites()
                if sites:
                    return sites
            except Exception as e:
                logger.warning(f"Failed to load sites from PostgreSQL: {e}, trying InfluxDB")
        
        # Try InfluxDB as fallback
        if self._influx_storage:
            try:
                sites = self._influx_storage.get_all_sites()
                if sites:
                    return sites
            except Exception as e:
                logger.warning(f"Failed to load sites from InfluxDB: {e}, falling back to files")

        # Fallback to files (backward compatibility)
        # Only if InfluxDB returned empty and we have files
        if not self.site_rules_dir or not self.site_rules_dir.exists():
            return []

        sites = []
        for config_file in self.site_rules_dir.glob("*_config.yaml"):
            try:
                site_id = config_file.stem.replace("_config", "")
                # Check if site is marked as deleted in InfluxDB first
                if self._influx_storage:
                    site_data = self._influx_storage.get_site(site_id)
                    if not site_data:  # Site is deleted or doesn't exist
                        continue
                site_info = self.get_site(site_id)
                if site_info:
                    sites.append(site_info)
            except Exception as e:
                logger.warning(f"Failed to load site from {config_file}: {e}")

        return sites

    def get_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        """
        Get site information by site_id from PostgreSQL (preferred), InfluxDB (fallback), or files

        Args:
            site_id: Site ID

        Returns:
            Site information dictionary or None if not found
        """
        # Check cache first
        if site_id in self._site_configs_cache:
            return self._site_configs_cache[site_id].copy()

        # Try PostgreSQL first (primary storage)
        if self._postgres_storage:
            try:
                site_data = self._postgres_storage.get_site(site_id)
                if site_data:
                    # Cache the result
                    self._site_configs_cache[site_id] = site_data
                    return site_data.copy()
            except Exception as e:
                logger.warning(f"Failed to load site from PostgreSQL: {e}, trying InfluxDB")

        # Try InfluxDB as fallback
        if self._influx_storage:
            try:
                site_data = self._influx_storage.get_site(site_id)
                if site_data:
                    # Cache the result
                    self._site_configs_cache[site_id] = site_data
                    # Sync to PostgreSQL if available
                    if self._postgres_storage:
                        try:
                            self._postgres_storage.save_site(site_data)
                        except Exception as e:
                            logger.warning(f"Failed to sync site to PostgreSQL: {e}")
                    return site_data.copy()
            except Exception as e:
                logger.warning(f"Failed to load site from InfluxDB: {e}, trying files")

        # Fallback to files (backward compatibility)
        if not self.site_rules_dir:
            return None

        # Load from file
        config_file = self.site_rules_dir / f"{site_id}_config.yaml"
        if not config_file.exists():
            return None

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            
            # Add site_id if not present
            if "site_id" not in config:
                config["site_id"] = site_id

            # Cache the result
            self._site_configs_cache[site_id] = config
            
            # Also save to InfluxDB for future use
            if self._influx_storage:
                try:
                    self._influx_storage.save_site(config)
                except Exception as e:
                    logger.warning(f"Failed to sync site to InfluxDB: {e}")
            
            return config.copy()
        except Exception as e:
            logger.error(f"Failed to load site config for {site_id}: {e}", exc_info=True)
            return None

    def get_site_rules(self, site_id: str) -> List[Dict[str, Any]]:
        """Get site-specific rules (delegated to SiteRuleManager)."""
        return self._site_rule_manager.get_site_rules(site_id)

    def add_site_rule(self, site_id: str, rule: Dict[str, Any], check_conflicts: bool = True) -> Tuple[bool, Optional[str]]:
        """Add a rule to a site (delegated to SiteRuleManager). Clears rule-engine cache on success."""
        success, err = self._site_rule_manager.add_site_rule(site_id, rule, check_conflicts)
        if success:
            try:
                from .dependencies import get_app_state
                app_state = get_app_state()
                rule_engine = app_state.get("rule_engine")
                if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                    rule_engine.site_rule_manager.reload_site_rules(site_id)
                    logger.debug(f"Cleared rule engine cache for site {site_id}")
            except Exception as e:
                logger.warning(f"Failed to clear rule engine cache: {e}")
        return success, err

    def update_site_rule(self, site_id: str, rule_id: str, rule: Dict[str, Any]) -> bool:
        """Update an existing rule (delegated to SiteRuleManager)."""
        return self._site_rule_manager.update_site_rule(site_id, rule_id, rule)

    def delete_site_rule(self, site_id: str, rule_id: str) -> bool:
        """Delete a rule from a site (delegated to SiteRuleManager)."""
        return self._site_rule_manager.delete_site_rule(site_id, rule_id)

    def site_exists(self, site_id: str) -> bool:
        """
        Check if site exists
        Checks PostgreSQL (primary), InfluxDB (fallback), files, and bucket existence
        Always queries fresh data, ignoring cache

        Args:
            site_id: Site ID

        Returns:
            True if site exists, False otherwise
        """
        # Clear cache for this site to ensure fresh check
        self._site_configs_cache.pop(site_id, None)
        
        # Check PostgreSQL first (primary storage)
        if self._postgres_storage:
            try:
                site_data = self._postgres_storage.get_site(site_id)
                if site_data:
                    logger.debug(f"Site {site_id} exists in PostgreSQL")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check site in PostgreSQL: {e}")
        
        # Check InfluxDB (fallback)
        if self._influx_storage:
            try:
                site_data = self._influx_storage.get_site(site_id)
                if site_data:
                    logger.debug(f"Site {site_id} exists in InfluxDB")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check site in InfluxDB: {e}")

        # Check files (backward compatibility)
        if self.site_rules_dir:
            config_file = self.site_rules_dir / f"{site_id}_config.yaml"
            if config_file.exists():
                logger.debug(f"Site {site_id} exists in files")
                return True
        
        # Also check if bucket exists (in case site config was deleted but bucket remains)
        # This prevents orphaned buckets from blocking site creation
        if self._container_manager:
            try:
                container = self._container_manager.get_container(site_id, auto_create=False)
                if container and container.exists():
                    # Bucket exists but site config doesn't - this is an orphaned bucket
                    # We'll allow site creation to proceed and clean up the bucket
                    logger.warning(f"Found orphaned bucket for site {site_id} (site config missing)")
                    return False  # Return False to allow site recreation
            except Exception as e:
                logger.debug(f"Error checking bucket existence for site {site_id}: {e}")
        
        logger.debug(f"Site {site_id} does not exist")
        return False

    def reload_site(self, site_id: str):
        """Reload site configuration and rule cache for a site."""
        if site_id in self._site_configs_cache:
            del self._site_configs_cache[site_id]
        self._site_rule_manager.reload_site_rules(site_id)
        logger.info(f"Reloaded site configuration for {site_id}")

    def reload_all_sites(self):
        """Reload all site configurations and rule caches."""
        self._site_configs_cache.clear()
        self._site_rule_manager.reload_site_rules(None)
        logger.info("Reloaded all site configurations")

    def clear_site_rules_cache(self, site_id: Optional[str] = None) -> None:
        """Clear rule cache for a site or all sites (for routes / rule-engine integration)."""
        self._site_rule_manager.reload_site_rules(site_id)

    def create_site(self, site_data: Dict[str, Any]) -> bool:
        """
        Create a new site configuration
        Saves to PostgreSQL (primary), InfluxDB (secondary), and optionally to files (backward compatibility)

        Args:
            site_data: Dictionary containing site configuration data

        Returns:
            True if site was created successfully, False otherwise
        """
        # Ensure directory exists if site_rules_dir is configured
        if self.site_rules_dir:
            self.site_rules_dir.mkdir(parents=True, exist_ok=True)

        site_id = site_data.get("site_id")
        if not site_id:
            logger.error("site_id is required")
            return False

        # Clear cache before checking to ensure fresh data
        self._site_configs_cache.pop(site_id, None)
        logger.debug(f"Cleared cache for site {site_id} before create_site check")

        # Check if site already exists
        if self.site_exists(site_id):
            logger.warning(f"Site {site_id} already exists (checked after cache clear)")
            return False

        # Prepare config data
        config = {
            "site_id": site_id,
            "site_name": site_data.get("site_name", site_id),
            "location": site_data.get("location", ""),
            "timezone": site_data.get("timezone", "UTC"),
            "climate": site_data.get("climate", ""),
        }

        # Add optional fields
        if "latitude" in site_data:
            config["latitude"] = site_data["latitude"]
        if "longitude" in site_data:
            config["longitude"] = site_data["longitude"]
        if "country" in site_data:
            config["country"] = site_data["country"]
        if "state" in site_data:
            config["state"] = site_data["state"]

        # Add default settings
        config["settings"] = {
            "data_collection_interval": 30,
            "alarm_cooldown_period": 300,
            "max_alarm_rate": 10,
            "enable_cross_site_analysis": True,
        }

        # Add default device configurations
        config["devices"] = {
            "BMS": {"enabled": True, "collection_interval": 30},
            "PCS": {"enabled": True, "collection_interval": 30},
            "UPS": {"enabled": False},
            "TMS": {"enabled": True, "collection_interval": 60},
        }
        config["devices_config"] = config["devices"]  # Also set devices_config for compatibility

        # Save to PostgreSQL (primary storage) - preferred
        if self._postgres_storage:
            try:
                if not self._postgres_storage.save_site(config):
                    logger.error(f"Failed to save site to PostgreSQL: {site_id}")
                    return False
                logger.info(f"Created site in PostgreSQL: {site_id}")
            except Exception as e:
                logger.error(f"Error saving site to PostgreSQL: {e}", exc_info=True)
                return False
        elif not self._influx_storage:
            logger.error("Neither PostgreSQL nor InfluxDB storage configured, cannot create site")
            return False

        # Also save to InfluxDB (secondary storage) for backward compatibility
        if self._influx_storage:
            try:
                if not self._influx_storage.save_site(config):
                    logger.warning(f"Failed to save site to InfluxDB: {site_id} (non-fatal)")
                else:
                    logger.info(f"Synced site to InfluxDB: {site_id}")
            except Exception as e:
                logger.warning(f"Error syncing site to InfluxDB: {e} (non-fatal)", exc_info=True)

        # Also save to file (backward compatibility, optional)
        if self.site_rules_dir:
            config_file = self.site_rules_dir / f"{site_id}_config.yaml"
            try:
                self.site_rules_dir.mkdir(parents=True, exist_ok=True)
                with open(config_file, "w", encoding="utf-8") as f:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                logger.info(f"Created site config file: {site_id}")
            except Exception as e:
                logger.warning(f"Failed to create site config file for {site_id}: {e}")
        
        # Clear cache for this site
        if site_id in self._site_configs_cache:
            del self._site_configs_cache[site_id]
        
        logger.info(f"Created site configuration for {site_id}")
        return True
    
    def load_universal_rules_to_site(self, site_id: str, universal_rules_file: str = "config/rules_universal.yaml") -> int:
        """Load EMS (site-level) rules from file into site (delegated to SiteRuleManager)."""
        return self._site_rule_manager.load_universal_rules_to_site(site_id, universal_rules_file)

    def create_device_rules(self, device_id: str, device_type: str, site_id: str) -> int:
        """Create rules for a device by type (delegated to SiteRuleManager)."""
        return self._site_rule_manager.create_device_rules(device_id, device_type, site_id)

    def delete_site(self, site_id: str) -> bool:
        """
        Delete a site configuration and its rules file

        Args:
            site_id: Site ID to delete

        Returns:
            True if site was deleted successfully, False otherwise
        """
        if not self.site_rules_dir:
            logger.error("Site rules directory not configured")
            return False

        if not self.site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            # Delete from PostgreSQL (primary storage)
            if self._postgres_storage:
                try:
                    if self._postgres_storage.delete_site(site_id):
                        logger.info(f"Deleted site from PostgreSQL: {site_id}")
                except Exception as e:
                    logger.error(f"Error deleting site from PostgreSQL: {e}", exc_info=True)
            
            # Also delete from InfluxDB (secondary storage)
            if self._influx_storage:
                try:
                    if self._influx_storage.delete_site(site_id):
                        logger.info(f"Deleted site from InfluxDB: {site_id}")
                except Exception as e:
                    logger.warning(f"Error deleting site from InfluxDB: {e} (non-fatal)", exc_info=True)

            # Also delete files (backward compatibility)
            if self.site_rules_dir:
                config_file = self.site_rules_dir / f"{site_id}_config.yaml"
                if config_file.exists():
                    config_file.unlink()
                    logger.info(f"Deleted site config file: {config_file}")

                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    rules_file.unlink()
                    logger.info(f"Deleted site rules file: {rules_file}")

            # Clear cache
            if site_id in self._site_configs_cache:
                del self._site_configs_cache[site_id]
            self._site_rule_manager.reload_site_rules(site_id)

            logger.info(f"Successfully deleted site {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete site {site_id}: {e}", exc_info=True)
            return False

    def update_site(self, site_id: str, site_data: Dict[str, Any]) -> bool:
        """
        Update site configuration

        Args:
            site_id: Site ID to update
            site_data: Dictionary containing updated site configuration data

        Returns:
            True if site was updated successfully, False otherwise
        """
        if not self.site_rules_dir:
            logger.error("Site rules directory not configured")
            return False

        if not self.site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            # Load existing config
            config_file = self.site_rules_dir / f"{site_id}_config.yaml"
            existing_config = {}
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    existing_config = yaml.safe_load(f) or {}

            # Merge with new data (don't overwrite site_id)
            updated_config = {**existing_config, **site_data}
            updated_config["site_id"] = site_id  # Ensure site_id is preserved

            # Save to PostgreSQL (primary storage)
            if self._postgres_storage:
                try:
                    if self._postgres_storage.save_site(updated_config):
                        logger.info(f"Updated site in PostgreSQL: {site_id}")
                    else:
                        logger.warning(f"Failed to update site in PostgreSQL: {site_id}")
                except Exception as e:
                    logger.error(f"Error updating site in PostgreSQL: {e}", exc_info=True)
            
            # Also save to InfluxDB (secondary storage)
            if self._influx_storage:
                try:
                    if self._influx_storage.save_site(updated_config):
                        logger.info(f"Synced site to InfluxDB: {site_id}")
                    else:
                        logger.warning(f"Failed to sync site to InfluxDB: {site_id} (non-fatal)")
                except Exception as e:
                    logger.warning(f"Error syncing site to InfluxDB: {e} (non-fatal)", exc_info=True)

            # Also update file (backward compatibility)
            if self.site_rules_dir:
                config_file = self.site_rules_dir / f"{site_id}_config.yaml"
                try:
                    with open(config_file, "w", encoding="utf-8") as f:
                        yaml.dump(updated_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                    logger.info(f"Updated site config file: {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to update site config file for {site_id}: {e}")

            # Clear cache
            if site_id in self._site_configs_cache:
                del self._site_configs_cache[site_id]

            logger.info(f"Updated site configuration for {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update site config for {site_id}: {e}", exc_info=True)
            return False

