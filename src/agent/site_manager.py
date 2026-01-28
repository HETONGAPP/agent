"""
Site Manager
Manages site configurations and provides site-related operations
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import yaml

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
        self._site_rules_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._postgres_storage = postgres_metadata_storage  # Primary storage
        self._influx_storage = influx_metadata_storage  # Secondary storage (for backward compatibility)
        self._container_manager = container_manager

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
        """
        Get site-specific rules
        Merges rules from PostgreSQL (primary) and InfluxDB (container) to ensure all rules are included
        Global rules are loaded from file, site rules are loaded from PostgreSQL first, then InfluxDB, then file as fallback

        Args:
            site_id: Site ID

        Returns:
            List of site-specific rules (merged from all sources)
        """
        # Check cache first
        if site_id in self._site_rules_cache:
            return self._site_rules_cache[site_id].copy()

        all_rules = []
        rule_ids_seen = set()

        # Get rules from PostgreSQL (primary storage) - THIS IS THE SOURCE OF TRUTH
        postgres_rules = []
        if self._postgres_storage:
            try:
                postgres_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                if postgres_rules:
                    logger.info(f"✓ Loaded {len(postgres_rules)} rules from PostgreSQL (database) for site {site_id} - these are the ACTUAL rules used for alarms")
                    # Add PostgreSQL rules to result - these take priority over YAML file
                    for rule in postgres_rules:
                        rule_id = rule.get("id")
                        if rule_id and rule_id not in rule_ids_seen:
                            all_rules.append(rule)
                            rule_ids_seen.add(rule_id)
                            # Log rule details to confirm database values are used
                            condition = rule.get("condition", {})
                            if condition.get("type") == "threshold":
                                logger.debug(
                                    f"  Rule {rule_id}: {condition.get('field')} {condition.get('operator')} {condition.get('value')} "
                                    f"(from database, enabled={rule.get('enabled', True)})"
                                )
            except Exception as e:
                logger.warning(f"Failed to load rules from PostgreSQL for site {site_id}: {e}, trying InfluxDB")

        # Get rules from InfluxDB container (secondary storage) and merge
        if self._container_manager:
            try:
                container = self._container_manager.get_container(site_id, auto_create=False)
                if container:
                    influxdb_rules = container.query_rules()
                    if influxdb_rules:
                        logger.debug(f"Loaded {len(influxdb_rules)} rules from InfluxDB for site {site_id}")
                        # Merge InfluxDB rules (add only if not already in PostgreSQL rules)
                        for rule in influxdb_rules:
                            rule_id = rule.get("id")
                            if rule_id and rule_id not in rule_ids_seen:
                                all_rules.append(rule)
                                rule_ids_seen.add(rule_id)
                                # Sync to PostgreSQL if available (for future queries)
                                if self._postgres_storage:
                                    try:
                                        self._postgres_storage.save_rule(site_id, rule)
                                    except Exception as e:
                                        logger.debug(f"Failed to sync rule {rule_id} to PostgreSQL: {e}")
            except Exception as e:
                logger.warning(f"Failed to load rules from InfluxDB for site {site_id}: {e}")

        # If we have rules from database, return them (database rules are the source of truth)
        if all_rules:
            # Cache the result
            self._site_rules_cache[site_id] = all_rules
            logger.info(
                f"✓ Using {len(all_rules)} rules from DATABASE for site {site_id} "
                f"(PostgreSQL: {len(postgres_rules)}, InfluxDB: {len(all_rules) - len(postgres_rules)})"
            )
            return all_rules.copy()

        # Fallback to file ONLY if database has no rules (YAML is just initial values)
        logger.warning(
            f"No rules found in database for site {site_id}, falling back to YAML file "
            f"(YAML file contains only initial values, update rules via frontend to save to database)"
        )
        if not self.site_rules_dir:
            return []

        rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
        if not rules_file.exists():
            logger.debug(f"No site-specific rules file found for {site_id}")
            return []

        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            rules = config.get("rules", [])
            
            # Cache the result
            self._site_rules_cache[site_id] = rules
            if rules:
                logger.warning(f"⚠ Using {len(rules)} rules from YAML FILE for site {site_id} (initial values only, not updated rules)")
            return rules.copy()
        except Exception as e:
            logger.error(f"Failed to load site rules from file for {site_id}: {e}", exc_info=True)
            return []

    def add_site_rule(self, site_id: str, rule: Dict[str, Any], check_conflicts: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Add a rule to a site's rules file

        Args:
            site_id: Site ID
            rule: Rule configuration dictionary
            check_conflicts: If True, check for conflicts with existing rules

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            If success is False, error_message contains the reason
        """
        if not self.site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False, f"Site {site_id} does not exist"

        try:
            rule_id = rule.get("id")
            if not rule_id:
                logger.error("Rule ID is required")
                return False, "Rule ID is required"

            logger.info(f"Adding rule {rule_id} to site {site_id}")

            # Get all existing rules for conflict checking
            existing_rules = []
            
            # Get rules from PostgreSQL (primary source)
            if self._postgres_storage:
                try:
                    all_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                    if all_rules:
                        existing_rules.extend(all_rules)
                        logger.debug(f"Loaded {len(all_rules)} rules from PostgreSQL for site {site_id}")
                except Exception as e:
                    logger.warning(f"Error loading rules from PostgreSQL: {e}")

            # Also get rules from file if site_rules_dir is configured (backward compatibility)
            if self.site_rules_dir:
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    try:
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                            file_rules = config.get("rules", [])
                            # Only add rules not already in existing_rules (avoid duplicates)
                            existing_rule_ids = {r.get("id") for r in existing_rules}
                            for file_rule in file_rules:
                                if file_rule.get("id") not in existing_rule_ids:
                                    existing_rules.append(file_rule)
                        logger.debug(f"Loaded {len(file_rules)} rules from file for site {site_id}")
                    except Exception as e:
                        logger.warning(f"Error loading rules from file: {e}")

            logger.debug(f"Total existing rules for conflict checking: {len(existing_rules)}")

            # Check if rule already exists (by ID) - do this first before conflict checking
            for existing_rule in existing_rules:
                if existing_rule.get("id") == rule_id:
                    logger.warning(f"Rule with ID {rule_id} already exists for site {site_id}")
                    return False, f"Rule with ID '{rule_id}' already exists. Please use a different ID or update the existing rule."

            # Check if rule already exists (by ID) - do this first before conflict checking
            for existing_rule in existing_rules:
                if existing_rule.get("id") == rule_id:
                    logger.warning(f"Rule with ID {rule_id} already exists for site {site_id}")
                    return False, f"Rule with ID '{rule_id}' already exists. Please use a different ID or update the existing rule."

            # Check for conflicts if enabled (skip ID duplicate check since we already did it above)
            if check_conflicts and existing_rules:
                try:
                    from ..rule_engine.conflict_detector import RuleConflictDetector
                    
                    conflicts = RuleConflictDetector.detect_conflicts(rule, existing_rules, strict_mode=True)
                    
                    # Filter out ID duplicate conflicts since we already checked for that
                    conflicts = [c for c in conflicts if c.get("type") != "id_duplicate"]
                    
                    # Check for critical errors (logical contradiction)
                    error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
                    if error_conflicts:
                        error_message = RuleConflictDetector.format_conflicts(error_conflicts)
                        logger.warning(f"Rule conflicts detected for {rule_id}:\n{error_message}")
                        return False, error_message
                    
                    # Log warnings but allow rule addition
                    warning_conflicts = [c for c in conflicts if c.get("severity") == "warning"]
                    if warning_conflicts:
                        warning_message = RuleConflictDetector.format_conflicts(warning_conflicts)
                        logger.warning(f"Rule warnings for {rule_id}:\n{warning_message}")
                        # Store warnings in rule metadata for later reference
                        if "metadata" not in rule:
                            rule["metadata"] = {}
                        rule["metadata"]["_conflict_warnings"] = warning_conflicts
                except ImportError as e:
                    logger.warning(f"Failed to import conflict detector: {e}. Skipping conflict check.")
                except Exception as e:
                    logger.error(f"Error during conflict detection: {e}", exc_info=True)
                    # Don't block rule addition if conflict detection fails, but log the error

            # Ensure rule has consistent alarm_type in metadata
            if "metadata" not in rule:
                rule["metadata"] = {}
            
            # If alarm_type is not set, generate it from rule name
            if "alarm_type" not in rule.get("metadata", {}):
                rule_name = rule.get("name", "Unknown")
                alarm_type = rule_name.lower().replace(" ", "_").replace("-", "_")
                rule["metadata"]["alarm_type"] = alarm_type
                logger.debug(f"Auto-generated alarm_type '{alarm_type}' from rule name '{rule_name}'")

            # Save to PostgreSQL (primary storage)
            if self._postgres_storage:
                try:
                    if self._postgres_storage.save_rule(site_id, rule):
                        logger.debug(f"Saved rule {rule_id} to PostgreSQL for site {site_id}")
                    else:
                        logger.error(f"Failed to save rule {rule_id} to PostgreSQL for site {site_id}")
                        return False, f"Failed to save rule {rule_id} to PostgreSQL"
                except Exception as e:
                    logger.error(f"Failed to save rule to PostgreSQL for site {site_id}: {e}", exc_info=True)
                    return False, f"Failed to save rule to PostgreSQL: {str(e)}"
            else:
                logger.warning("PostgreSQL storage not configured, rule will not be persisted")

            # Also save to InfluxDB container (secondary storage) - dual write
            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=True)
                    if container:
                        container.write_rule(rule, flush=True)
                        logger.debug(f"Saved rule {rule_id} to InfluxDB container for site {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to save rule to InfluxDB container for site {site_id}: {e}")

            # Also save to file if site_rules_dir is configured (backward compatibility)
            if self.site_rules_dir:
                existing_rules.append(rule)
                config = {"rules": existing_rules}
                self.site_rules_dir.mkdir(parents=True, exist_ok=True)
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                with open(rules_file, "w", encoding="utf-8") as f:
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                logger.debug(f"Saved rule {rule_id} to file for site {site_id}")

            # Clear cache in SiteManager
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]
            
            # Also clear cache in SiteRuleManager if available
            # This ensures rule engine picks up the new rule immediately
            if self._container_manager:
                try:
                    from ..agent.dependencies import get_app_state
                    app_state = get_app_state()
                    rule_engine = app_state.get("rule_engine")
                    if rule_engine and hasattr(rule_engine, "site_rule_manager"):
                        rule_engine.site_rule_manager.reload_site_rules(site_id)
                        logger.debug(f"Cleared rule cache in SiteRuleManager for site {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to clear rule cache in SiteRuleManager: {e}")

            logger.info(f"Added rule {rule_id or 'unnamed'} to site {site_id}")
            return True, None
        except Exception as e:
            logger.error(f"Failed to add rule to site {site_id}: {e}", exc_info=True)
            return False, str(e)

    def update_site_rule(self, site_id: str, rule_id: str, rule: Dict[str, Any]) -> bool:
        """
        Update an existing rule in a site
        Updates rule in PostgreSQL (primary), InfluxDB container (secondary), and optionally in files (backward compatibility)

        Args:
            site_id: Site ID
            rule_id: Rule ID to update
            rule: Updated rule configuration dictionary

        Returns:
            True if rule was updated successfully, False otherwise
        """
        if not self.site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            # Ensure rule_id is preserved
            rule["id"] = rule_id

            # Ensure rule has consistent alarm_type in metadata
            if "metadata" not in rule:
                rule["metadata"] = {}
            
            # If alarm_type is not set, generate it from rule name
            if "alarm_type" not in rule.get("metadata", {}):
                rule_name = rule.get("name", "Unknown")
                alarm_type = rule_name.lower().replace(" ", "_").replace("-", "_")
                rule["metadata"]["alarm_type"] = alarm_type
                logger.debug(f"Auto-generated alarm_type '{alarm_type}' from rule name '{rule_name}'")

            # Find all device-specific rules that match this base rule
            # e.g., if updating RULE_BMS_006, also update RULE_BMS_006_BMS_001, RULE_BMS_006_BMS_002, etc.
            device_specific_rule_ids = []
            if self._postgres_storage:
                try:
                    all_site_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                    for existing_rule in all_site_rules:
                        existing_rule_id = existing_rule.get("id", "")
                        # Check if this is a device-specific rule that matches the base rule
                        # Pattern: RULE_BMS_006_BMS_001 should match base RULE_BMS_006
                        if existing_rule_id and existing_rule_id.startswith(f"{rule_id}_"):
                            device_specific_rule_ids.append(existing_rule_id)
                            logger.debug(f"Found device-specific rule {existing_rule_id} matching base rule {rule_id}")
                except Exception as e:
                    logger.warning(f"Failed to find device-specific rules for {rule_id} in site {site_id}: {e}")

            # Try to update in PostgreSQL first (primary storage)
            rule_found = False
            if self._postgres_storage:
                try:
                    existing_rule = self._postgres_storage.get_rule(site_id, rule_id)
                    if existing_rule:
                        # Rule exists, update it
                        if self._postgres_storage.save_rule(site_id, rule):
                            rule_found = True
                            logger.debug(f"Updated rule {rule_id} in PostgreSQL for site {site_id}")
                        else:
                            logger.warning(f"Failed to update rule {rule_id} in PostgreSQL for site {site_id}")
                    else:
                        logger.debug(f"Rule {rule_id} not found in PostgreSQL for site {site_id}, checking InfluxDB")
                except Exception as e:
                    logger.warning(f"Failed to update rule in PostgreSQL for site {site_id}: {e}")

            # Update all device-specific rules that match this base rule
            device_specific_updated = 0
            if device_specific_rule_ids and self._postgres_storage:
                for device_rule_id in device_specific_rule_ids:
                    try:
                        # Create a copy of the rule with the device-specific ID
                        device_rule = rule.copy()
                        device_rule["id"] = device_rule_id
                        # Preserve device_ids from existing rule
                        existing_device_rule = self._postgres_storage.get_rule(site_id, device_rule_id)
                        if existing_device_rule and existing_device_rule.get("device_ids"):
                            device_rule["device_ids"] = existing_device_rule["device_ids"]
                        
                        if self._postgres_storage.save_rule(site_id, device_rule):
                            device_specific_updated += 1
                            logger.info(f"Updated device-specific rule {device_rule_id} for site {site_id}")
                        else:
                            logger.warning(f"Failed to update device-specific rule {device_rule_id} in PostgreSQL")
                    except Exception as e:
                        logger.warning(f"Failed to update device-specific rule {device_rule_id}: {e}")
            
            if device_specific_updated > 0:
                logger.info(f"Updated {device_specific_updated} device-specific rules matching base rule {rule_id}")

            # Also update in InfluxDB container (secondary storage)
            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=True)
                    if container:
                        container.write_rule(rule, flush=True)
                        logger.debug(f"Updated rule {rule_id} in InfluxDB container for site {site_id}")
                        
                        # Also update device-specific rules in container
                        for device_rule_id in device_specific_rule_ids:
                            try:
                                device_rule = rule.copy()
                                device_rule["id"] = device_rule_id
                                # Get device_ids from existing rule if available
                                if self._postgres_storage:
                                    existing_device_rule = self._postgres_storage.get_rule(site_id, device_rule_id)
                                    if existing_device_rule and existing_device_rule.get("device_ids"):
                                        device_rule["device_ids"] = existing_device_rule["device_ids"]
                                container.write_rule(device_rule, flush=True)
                                logger.debug(f"Updated device-specific rule {device_rule_id} in InfluxDB container")
                            except Exception as e:
                                logger.warning(f"Failed to update device-specific rule {device_rule_id} in container: {e}")
                except Exception as e:
                    logger.warning(f"Failed to update rule in InfluxDB container for site {site_id}: {e}")

            # Also check/update in file if site_rules_dir is configured (backward compatibility)
            # This handles cases where rule exists in file but not in container yet
            if self.site_rules_dir:
                try:
                    rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                    if rules_file.exists():
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                            existing_rules = config.get("rules", [])

                        # Find and update the rule
                        file_rule_found = False
                        for i, existing_rule in enumerate(existing_rules):
                            if existing_rule.get("id") == rule_id:
                                existing_rules[i] = rule
                                file_rule_found = True
                                break

                        if file_rule_found:
                            # Save to file
                            config = {"rules": existing_rules}
                            with open(rules_file, "w", encoding="utf-8") as f:
                                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                            logger.debug(f"Updated rule {rule_id} in file for site {site_id}")
                            
                            # If container update failed, also write to container now
                            if not rule_found and self._container_manager:
                                try:
                                    container = self._container_manager.get_container(site_id, auto_create=True)
                                    if container:
                                        container.write_rule(rule, flush=True)
                                        logger.debug(f"Wrote rule {rule_id} to container from file update")
                                except Exception as e:
                                    logger.warning(f"Failed to write rule to container after file update: {e}")
                            
                            rule_found = file_rule_found
                    else:
                        logger.debug(f"Rules file not found for site {site_id}, skipping file update")
                except Exception as e:
                    logger.warning(f"Failed to update rule in file for site {site_id}: {e}")

            if not rule_found:
                logger.warning(f"Rule with ID {rule_id} not found for site {site_id}")
                return False

            # Clear related alarms when rule is updated
            # This ensures that old alarms based on the previous rule configuration are removed
            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=False)
                    if container:
                        # Delete alarms by rule_id (matches both metadata.rule_id and alarm_id prefix)
                        deleted_count = container.delete_alarms(rule_id=rule_id)
                        
                        # Also try to delete by base rule_id if rule_id contains device suffix
                        # e.g., if rule_id is "RULE_BMS_006_BMS_001", also try "RULE_BMS_006"
                        # This handles cases where alarms were created with base rule_id
                        if "_" in rule_id and rule_id.startswith("RULE_"):
                            # Extract base rule_id (e.g., "RULE_BMS_006" from "RULE_BMS_006_BMS_001")
                            parts = rule_id.split("_")
                            if len(parts) >= 3:
                                # Try base rule_id (first 3 parts: RULE_BMS_006)
                                base_rule_id = "_".join(parts[:3])
                                if base_rule_id != rule_id:
                                    base_deleted = container.delete_alarms(rule_id=base_rule_id)
                                    if base_deleted > 0:
                                        logger.info(f"Cleared {base_deleted} additional alarms for base rule {base_rule_id} in site {site_id}")
                                        deleted_count += base_deleted
                        
                        if deleted_count > 0:
                            logger.info(f"Cleared {deleted_count} old alarms for updated rule {rule_id} in site {site_id}")
                        else:
                            logger.debug(f"No alarms found to delete for rule {rule_id} in site {site_id} (may already be cleared or rule_id doesn't match)")
                except Exception as e:
                    logger.warning(f"Failed to clear old alarms for rule {rule_id} in site {site_id}: {e}")

            # Clear cache
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]

            logger.info(f"Updated rule {rule_id} for site {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update rule for site {site_id}: {e}", exc_info=True)
            return False

    def delete_site_rule(self, site_id: str, rule_id: str) -> bool:
        """
        Delete a rule from a site
        Deletes from PostgreSQL (primary), InfluxDB container (secondary), and optionally from files (backward compatibility)

        Args:
            site_id: Site ID
            rule_id: Rule ID to delete

        Returns:
            True if rule was deleted successfully, False otherwise
        """
        if not self.site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            deleted = False

            # Delete from PostgreSQL (primary storage)
            if self._postgres_storage:
                try:
                    if self._postgres_storage.delete_rule(site_id, rule_id):
                        deleted = True
                        logger.debug(f"Deleted rule {rule_id} from PostgreSQL for site {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete rule from PostgreSQL for site {site_id}: {e}")

            # Also delete from InfluxDB container (secondary storage)
            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=False)
                    if container:
                        container.delete_rule(rule_id)
                        logger.debug(f"Deleted rule {rule_id} from InfluxDB container for site {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete rule from InfluxDB container for site {site_id}: {e}")

            # Also delete from file if site_rules_dir is configured (backward compatibility)
            if self.site_rules_dir:
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    try:
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                            existing_rules = config.get("rules", [])

                        # Find and remove the rule
                        original_count = len(existing_rules)
                        existing_rules = [r for r in existing_rules if r.get("id") != rule_id]

                        if len(existing_rules) < original_count:
                            # Save to file
                            config = {"rules": existing_rules}
                            with open(rules_file, "w", encoding="utf-8") as f:
                                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                            logger.debug(f"Deleted rule {rule_id} from file for site {site_id}")
                            deleted = True
                    except Exception as e:
                        logger.warning(f"Failed to delete rule from file for site {site_id}: {e}")

            if not deleted:
                logger.warning(f"Rule with ID {rule_id} not found for site {site_id}")
                return False

            # Also delete from container (database) - dual write
            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=False)
                    if container:
                        container.delete_rule(rule_id)
                        logger.debug(f"Deleted rule {rule_id} from container for site {site_id}")
                except Exception as e:
                    logger.warning(f"Failed to delete rule from container for site {site_id}: {e}")

            # Clear cache
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]

            logger.info(f"Deleted rule {rule_id} from site {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete rule from site {site_id}: {e}", exc_info=True)
            return False

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
        """
        Reload site configuration from file

        Args:
            site_id: Site ID
        """
        if site_id in self._site_configs_cache:
            del self._site_configs_cache[site_id]
        if site_id in self._site_rules_cache:
            del self._site_rules_cache[site_id]
        logger.info(f"Reloaded site configuration for {site_id}")

    def reload_all_sites(self):
        """Reload all site configurations"""
        self._site_configs_cache.clear()
        self._site_rules_cache.clear()
        logger.info("Reloaded all site configurations")

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
        """
        Load only EMS (site-level) rules from file to site container database.
        Device-specific rules are created when devices are added.
        
        Args:
            site_id: Site ID
            universal_rules_file: Path to universal rules YAML file
            
        Returns:
            Number of rules loaded
        """
        if not self._container_manager:
            logger.warning(f"Cannot load universal rules: container manager not available")
            return 0
        
        try:
            # Load universal rules from file
            rules_file = Path(universal_rules_file)
            if not rules_file.exists():
                logger.warning(f"Universal rules file not found: {universal_rules_file}")
                return 0
            
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = yaml.safe_load(f)
            
            all_rules = rules_config.get("rules", [])
            if not all_rules:
                logger.warning(f"No rules found in universal rules file: {universal_rules_file}")
                return 0
            
            # Filter only EMS (site-level) rules
            ems_rules = []
            for rule in all_rules:
                rule_device_types = rule.get("device_types", [])
                # Only load rules that have EMS in device_types (site-level rules)
                if rule_device_types and "EMS" in rule_device_types:
                    ems_rules.append(rule)
            
            if not ems_rules:
                logger.info(f"No EMS rules found in universal rules file for site {site_id}")
                return 0
            
            # Get site container
            container = self._container_manager.get_container(site_id, auto_create=True)
            if not container:
                logger.error(f"Failed to get container for site {site_id}")
                return 0
            
            # Check if rules already exist
            existing_rules = container.query_rules()
            existing_rule_ids = {rule.get("id") for rule in existing_rules if rule.get("id")}
            
            # Write only EMS rules to container database
            loaded_count = 0
            skipped_count = 0
            for rule in ems_rules:
                rule_id = rule.get("id")
                if not rule_id:
                    logger.warning(f"Skipping rule without ID: {rule.get('name', 'Unknown')}")
                    continue
                
                # Skip if rule already exists
                if rule_id in existing_rule_ids:
                    skipped_count += 1
                    logger.debug(f"Rule {rule_id} already exists in site {site_id}, skipping")
                    continue
                
                # Write rule to container
                if container.write_rule(rule, flush=False):
                    loaded_count += 1
                    logger.debug(f"Loaded EMS rule {rule_id} to site {site_id}")
                else:
                    logger.warning(f"Failed to write rule {rule_id} to site {site_id}")
            
            # Flush remaining rules
            if loaded_count > 0:
                container.influx_client.write_api.write(
                    bucket=container.bucket,
                    org=container.influx_client.org,
                    record=container.influx_client._write_buffer
                )
                container.influx_client._write_buffer = []
            
            # Clear cache for this site
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]
            
            logger.info(f"Loaded {loaded_count} universal rules to site {site_id} (skipped {skipped_count} existing rules)")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Failed to load universal rules to site {site_id}: {e}", exc_info=True)
            return 0
    
    def create_device_rules(self, device_id: str, device_type: str, site_id: str) -> int:
        """
        Create rules for a specific device based on its device type.
        Each device gets its own copy of rules in the database with device_ids set.
        EMS rules are excluded as they are site-level only.
        
        Args:
            device_id: Device ID
            device_type: Device type (e.g., "BMS", "PCS")
            site_id: Site ID
            
        Returns:
            Number of rules created
        """
        # EMS is site-level only, don't create device-specific rules for EMS
        if device_type.upper() == "EMS":
            logger.info(f"EMS is site-level only, skipping device-specific rule creation for {device_id}")
            return 0
        
        if not self._container_manager:
            logger.warning(f"Cannot create device rules: container manager not available")
            return 0
        
        try:
            # Load universal rules from file
            rules_file = Path("config/rules_universal.yaml")
            if not rules_file.exists():
                logger.warning(f"Universal rules file not found: config/rules_universal.yaml")
                return 0
            
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = yaml.safe_load(f)
            
            all_rules = rules_config.get("rules", [])
            if not all_rules:
                logger.warning(f"No rules found in universal rules file")
                return 0
            
            # Filter rules applicable to this device type (exclude EMS rules)
            applicable_rules = []
            for rule in all_rules:
                rule_device_types = rule.get("device_types", [])
                # Skip EMS rules - they are site-level only
                if rule_device_types and "EMS" in rule_device_types:
                    continue
                # Only include rules that match this device type
                if rule_device_types and device_type.upper() in rule_device_types:
                    # Create a copy of the rule for this specific device
                    device_rule = rule.copy()
                    # Set device_ids to ensure rule only applies to this device
                    device_rule["device_ids"] = [device_id]
                    # Generate unique rule ID for this device
                    original_id = device_rule.get("id", "")
                    if original_id:
                        # Check if the rule ID already ends with the device_id to avoid duplicate concatenation
                        # e.g., if original_id is "RULE_BMS_001_BMS_001" and device_id is "BMS_001", 
                        # we should not append again
                        if original_id.endswith(f"_{device_id}"):
                            # Rule ID already contains device_id, use it as is
                            device_rule["id"] = original_id
                        else:
                            # Extract base rule ID if it already contains a device_id suffix from a previous run
                            # Pattern: RULE_{TYPE}_{NUM}_{DEVICE_ID} -> RULE_{TYPE}_{NUM}
                            # e.g., "RULE_BMS_001_BMS_001" -> "RULE_BMS_001"
                            parts = original_id.split("_")
                            # Check if last part matches device_id and second-to-last part matches device_type prefix
                            if len(parts) >= 4:
                                last_part = parts[-1]
                                # Check if last part is a device_id (could be BMS_001, PCS_001, etc.)
                                # If it matches the current device_id, extract base
                                if last_part == device_id:
                                    # Extract base: remove the last part (device_id)
                                    base_id = "_".join(parts[:-1])
                                    device_rule["id"] = f"{base_id}_{device_id}"
                                else:
                                    # Normal case: append device_id to original rule ID
                                    device_rule["id"] = f"{original_id}_{device_id}"
                            else:
                                # Normal case: append device_id to original rule ID
                                device_rule["id"] = f"{original_id}_{device_id}"
                    applicable_rules.append(device_rule)
            
            if not applicable_rules:
                logger.info(f"No applicable rules found for device {device_id} (type={device_type})")
                return 0
            
            # Get site container
            container = self._container_manager.get_container(site_id, auto_create=True)
            if not container:
                logger.error(f"Failed to get container for site {site_id}")
                return 0
            
            # Check existing rules for this device
            existing_rules = container.query_rules()
            existing_rule_ids = {rule.get("id") for rule in existing_rules if rule.get("id")}
            
            # Write device-specific rules to both PostgreSQL (primary) and InfluxDB container (secondary)
            created_count = 0
            for rule in applicable_rules:
                rule_id = rule.get("id")
                if not rule_id:
                    continue
                
                # Skip if rule already exists for this device
                if rule_id in existing_rule_ids:
                    logger.debug(f"Rule {rule_id} already exists for device {device_id}, skipping")
                    continue
                
                # Save to PostgreSQL first (primary storage)
                if self._postgres_storage:
                    try:
                        if self._postgres_storage.save_rule(site_id, rule):
                            logger.debug(f"Saved rule {rule_id} to PostgreSQL for device {device_id}")
                        else:
                            logger.warning(f"Failed to save rule {rule_id} to PostgreSQL for device {device_id}")
                    except Exception as e:
                        logger.warning(f"Failed to save rule {rule_id} to PostgreSQL: {e}")
                
                # Also save to InfluxDB container (secondary storage) - dual write
                if container.write_rule(rule, flush=False):
                    created_count += 1
                    logger.debug(f"Created rule {rule_id} for device {device_id}")
            
            # Flush all rules at once
            container.flush_rules()
            
            # Clear cache for this site to ensure fresh data on next query
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]
            
            logger.info(f"Created {created_count} rules for device {device_id} (type={device_type}) in site {site_id}")
            return created_count
        except Exception as e:
            logger.error(f"Failed to create rules for device {device_id}: {e}", exc_info=True)
            return 0

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
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]

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

