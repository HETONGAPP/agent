"""
Agent-side site rule manager: persistence and CRUD for site rules.
Delegates 'site exists' checks to the provided callable; does not own site config.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class SiteRuleManager:
    """
    Manages site rule persistence and operations.
    Uses PostgreSQL (primary), InfluxDB container (secondary), and optional file fallback.
    """

    def __init__(
        self,
        site_rules_dir: Optional[Path],
        postgres_storage,
        influx_storage,
        container_manager,
        site_exists: Callable[[str], bool],
    ):
        self.site_rules_dir = site_rules_dir
        self._postgres_storage = postgres_storage
        self._influx_storage = influx_storage
        self._container_manager = container_manager
        self._site_exists = site_exists
        self._site_rules_cache: Dict[str, List[Dict[str, Any]]] = {}

    def reload_site_rules(self, site_id: Optional[str] = None) -> None:
        """Clear rule cache for a site or all sites."""
        if site_id:
            if site_id in self._site_rules_cache:
                del self._site_rules_cache[site_id]
                logger.info(f"✓ Cleared rule cache for site {site_id} (rules will be reloaded from database on next access)")
            else:
                logger.debug(f"Rule cache for site {site_id} was already empty")
        else:
            self._site_rules_cache.clear()
            logger.info("✓ Cleared all rule caches (rules will be reloaded from database on next access)")

    def get_site_rules(self, site_id: str) -> List[Dict[str, Any]]:
        """
        Get site-specific rules.
        Merges from PostgreSQL (primary) and InfluxDB container, with file fallback.
        """
        if site_id in self._site_rules_cache:
            return self._site_rules_cache[site_id].copy()

        all_rules = []
        rule_ids_seen = set()

        if self._postgres_storage:
            try:
                postgres_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                if postgres_rules:
                    logger.info(
                        f"✓ Loaded {len(postgres_rules)} rules from PostgreSQL (database) for site {site_id} "
                        "- these are the ACTUAL rules used for alarms"
                    )
                    for rule in postgres_rules:
                        rule_id = rule.get("id")
                        if rule_id and rule_id not in rule_ids_seen:
                            all_rules.append(rule)
                            rule_ids_seen.add(rule_id)
                            cond = rule.get("condition", {})
                            if cond.get("type") == "threshold":
                                logger.info(
                                    f"  Rule {rule_id}: {cond.get('field')} {cond.get('operator')} {cond.get('value')} "
                                    f"(from database, enabled={rule.get('enabled', True)}, device_ids={rule.get('device_ids', [])})"
                                )
            except Exception as e:
                logger.warning(f"Failed to load rules from PostgreSQL for site {site_id}: {e}, trying InfluxDB")

        if self._container_manager:
            try:
                container = self._container_manager.get_container(site_id, auto_create=False)
                if container:
                    influxdb_rules = container.query_rules()
                    if influxdb_rules:
                        logger.debug(f"Loaded {len(influxdb_rules)} rules from InfluxDB for site {site_id}")
                        for rule in influxdb_rules:
                            rule_id = rule.get("id")
                            if rule_id and rule_id not in rule_ids_seen:
                                all_rules.append(rule)
                                rule_ids_seen.add(rule_id)
                                if self._postgres_storage:
                                    try:
                                        self._postgres_storage.save_rule(site_id, rule)
                                    except Exception as e:
                                        logger.debug(f"Failed to sync rule {rule_id} to PostgreSQL: {e}")
            except Exception as e:
                logger.warning(f"Failed to load rules from InfluxDB for site {site_id}: {e}")

        if all_rules:
            self._site_rules_cache[site_id] = all_rules
            logger.info(f"✓ Using {len(all_rules)} rules from DATABASE for site {site_id}")
            return all_rules.copy()

        logger.warning(
            f"No rules found in database for site {site_id}, falling back to YAML file "
            "(YAML file contains only initial values, update rules via frontend to save to database)"
        )
        if not self.site_rules_dir or not self.site_rules_dir.exists():
            return []

        rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
        if not rules_file.exists():
            logger.debug(f"No site-specific rules file found for {site_id}")
            return []

        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            rules = config.get("rules", [])
            self._site_rules_cache[site_id] = rules
            if rules:
                logger.warning(
                    f"⚠ Using {len(rules)} rules from YAML FILE for site {site_id} "
                    "(initial values only, not updated rules)"
                )
            return rules.copy()
        except Exception as e:
            logger.error(f"Failed to load site rules from file for {site_id}: {e}", exc_info=True)
            return []

    def add_site_rule(
        self, site_id: str, rule: Dict[str, Any], check_conflicts: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """Add a rule for a site. Returns (success, error_message)."""
        if not self._site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False, f"Site {site_id} does not exist"

        try:
            rule_id = rule.get("id")
            if not rule_id:
                logger.error("Rule ID is required")
                return False, "Rule ID is required"

            logger.info(f"Adding rule {rule_id} to site {site_id}")

            existing_rules = []
            if self._postgres_storage:
                try:
                    all_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                    if all_rules:
                        existing_rules.extend(all_rules)
                except Exception as e:
                    logger.warning(f"Error loading rules from PostgreSQL: {e}")

            if self.site_rules_dir and self.site_rules_dir.exists():
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    try:
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                        file_rules = config.get("rules", [])
                        existing_rule_ids = {r.get("id") for r in existing_rules}
                        for file_rule in file_rules:
                            if file_rule.get("id") not in existing_rule_ids:
                                existing_rules.append(file_rule)
                    except Exception as e:
                        logger.warning(f"Error loading rules from file: {e}")

            for existing_rule in existing_rules:
                if existing_rule.get("id") == rule_id:
                    logger.warning(f"Rule with ID {rule_id} already exists for site {site_id}")
                    return False, f"Rule with ID '{rule_id}' already exists. Please use a different ID or update the existing rule."

            if check_conflicts and existing_rules:
                try:
                    from ..rule_engine.conflict_detector import RuleConflictDetector

                    conflicts = RuleConflictDetector.detect_conflicts(rule, existing_rules, strict_mode=True)
                    conflicts = [c for c in conflicts if c.get("type") != "id_duplicate"]
                    error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
                    if error_conflicts:
                        msg = RuleConflictDetector.format_conflicts(error_conflicts)
                        logger.warning(f"Rule conflicts detected for {rule_id}:\n{msg}")
                        return False, msg
                    warning_conflicts = [c for c in conflicts if c.get("severity") == "warning"]
                    if warning_conflicts:
                        msg = RuleConflictDetector.format_conflicts(warning_conflicts)
                        logger.warning(f"Rule warnings for {rule_id}:\n{msg}")
                        if "metadata" not in rule:
                            rule["metadata"] = {}
                        rule["metadata"]["_conflict_warnings"] = warning_conflicts
                except ImportError as e:
                    logger.warning(f"Failed to import conflict detector: {e}. Skipping conflict check.")
                except Exception as e:
                    logger.error(f"Error during conflict detection: {e}", exc_info=True)

            if "metadata" not in rule:
                rule["metadata"] = {}
            if "alarm_type" not in rule.get("metadata", {}):
                name = rule.get("name", "Unknown")
                alarm_type = name.lower().replace(" ", "_").replace("-", "_")
                rule["metadata"]["alarm_type"] = alarm_type

            if self._postgres_storage:
                try:
                    if not self._postgres_storage.save_rule(site_id, rule):
                        return False, f"Failed to save rule {rule_id} to PostgreSQL"
                except Exception as e:
                    logger.error(f"Failed to save rule to PostgreSQL for site {site_id}: {e}", exc_info=True)
                    return False, f"Failed to save rule to PostgreSQL: {str(e)}"
            else:
                logger.warning("PostgreSQL storage not configured, rule will not be persisted")

            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=True)
                    if container:
                        container.write_rule(rule, flush=True)
                except Exception as e:
                    logger.warning(f"Failed to save rule to InfluxDB container for site {site_id}: {e}")

            if self.site_rules_dir and self.site_rules_dir.exists():
                existing_rules.append(rule)
                self.site_rules_dir.mkdir(parents=True, exist_ok=True)
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                with open(rules_file, "w", encoding="utf-8") as f:
                    yaml.dump({"rules": existing_rules}, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            self.reload_site_rules(site_id)
            logger.info(f"Added rule {rule_id or 'unnamed'} to site {site_id}")
            return True, None
        except Exception as e:
            logger.error(f"Failed to add rule to site {site_id}: {e}", exc_info=True)
            return False, str(e)

    def update_site_rule(self, site_id: str, rule_id: str, rule: Dict[str, Any]) -> bool:
        """Update an existing rule for a site."""
        if not self._site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            rule["id"] = rule_id
            if "metadata" not in rule:
                rule["metadata"] = {}
            if "alarm_type" not in rule.get("metadata", {}):
                name = rule.get("name", "Unknown")
                rule["metadata"]["alarm_type"] = name.lower().replace(" ", "_").replace("-", "_")

            device_specific_rule_ids = []
            if self._postgres_storage:
                try:
                    all_site_rules = self._postgres_storage.get_rules_by_site(site_id, enabled_only=False)
                    for existing_rule in all_site_rules:
                        rid = existing_rule.get("id", "")
                        if rid and rid.startswith(f"{rule_id}_"):
                            device_specific_rule_ids.append(rid)
                except Exception as e:
                    logger.warning(f"Failed to find device-specific rules for {rule_id} in site {site_id}: {e}")

            rule_found = False
            if self._postgres_storage:
                try:
                    existing = self._postgres_storage.get_rule(site_id, rule_id)
                    if existing and self._postgres_storage.save_rule(site_id, rule):
                        rule_found = True
                except Exception as e:
                    logger.warning(f"Failed to update rule in PostgreSQL for site {site_id}: {e}")

            if device_specific_rule_ids and self._postgres_storage:
                for device_rule_id in device_specific_rule_ids:
                    try:
                        device_rule = rule.copy()
                        device_rule["id"] = device_rule_id
                        existing_device = self._postgres_storage.get_rule(site_id, device_rule_id)
                        if existing_device and existing_device.get("device_ids"):
                            device_rule["device_ids"] = existing_device["device_ids"]
                        if self._postgres_storage.save_rule(site_id, device_rule):
                            rule_found = True
                    except Exception as e:
                        logger.warning(f"Failed to update device-specific rule {device_rule_id}: {e}")

            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=True)
                    if container:
                        container.write_rule(rule, flush=True)
                        for device_rule_id in device_specific_rule_ids:
                            try:
                                dr = rule.copy()
                                dr["id"] = device_rule_id
                                if self._postgres_storage:
                                    ed = self._postgres_storage.get_rule(site_id, device_rule_id)
                                    if ed and ed.get("device_ids"):
                                        dr["device_ids"] = ed["device_ids"]
                                container.write_rule(dr, flush=True)
                            except Exception as e:
                                logger.warning(f"Failed to update device-specific rule {device_rule_id} in container: {e}")
                except Exception as e:
                    logger.warning(f"Failed to update rule in InfluxDB container for site {site_id}: {e}")

            if self.site_rules_dir:
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    try:
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                        existing_rules = config.get("rules", [])
                        file_rule_found = False
                        for i, er in enumerate(existing_rules):
                            if er.get("id") == rule_id:
                                existing_rules[i] = rule
                                file_rule_found = True
                                break
                        if file_rule_found:
                            with open(rules_file, "w", encoding="utf-8") as f:
                                yaml.dump(
                                    {"rules": existing_rules},
                                    f,
                                    default_flow_style=False,
                                    allow_unicode=True,
                                    sort_keys=False,
                                )
                            if not rule_found and self._container_manager:
                                try:
                                    cont = self._container_manager.get_container(site_id, auto_create=True)
                                    if cont:
                                        cont.write_rule(rule, flush=True)
                                except Exception:
                                    pass
                            rule_found = rule_found or file_rule_found
                    except Exception as e:
                        logger.warning(f"Failed to update rule in file for site {site_id}: {e}")

            if not rule_found:
                logger.warning(f"Rule with ID {rule_id} not found for site {site_id}")
                return False

            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=False)
                    if container:
                        container.delete_alarms(rule_id=rule_id)
                        if "_" in rule_id and rule_id.startswith("RULE_"):
                            parts = rule_id.split("_")
                            if len(parts) >= 3:
                                base_rule_id = "_".join(parts[:3])
                                if base_rule_id != rule_id:
                                    container.delete_alarms(rule_id=base_rule_id)
                except Exception as e:
                    logger.warning(f"Failed to clear alarms for rule {rule_id} in site {site_id}: {e}")

            self.reload_site_rules(site_id)
            logger.info(f"Updated rule {rule_id} for site {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update rule for site {site_id}: {e}", exc_info=True)
            return False

    def delete_site_rule(self, site_id: str, rule_id: str) -> bool:
        """Delete a rule from a site."""
        if not self._site_exists(site_id):
            logger.warning(f"Site {site_id} does not exist")
            return False

        try:
            deleted = False
            if self._postgres_storage:
                try:
                    if self._postgres_storage.delete_rule(site_id, rule_id):
                        deleted = True
                except Exception as e:
                    logger.warning(f"Failed to delete rule from PostgreSQL for site {site_id}: {e}")

            if self._container_manager:
                try:
                    container = self._container_manager.get_container(site_id, auto_create=False)
                    if container:
                        container.delete_rule(rule_id)
                        deleted = True
                except Exception as e:
                    logger.warning(f"Failed to delete rule from InfluxDB container for site {site_id}: {e}")

            if self.site_rules_dir:
                rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
                if rules_file.exists():
                    try:
                        with open(rules_file, "r", encoding="utf-8") as f:
                            config = yaml.safe_load(f) or {}
                        existing_rules = [r for r in config.get("rules", []) if r.get("id") != rule_id]
                        if len(existing_rules) < len(config.get("rules", [])):
                            with open(rules_file, "w", encoding="utf-8") as f:
                                yaml.dump(
                                    {"rules": existing_rules},
                                    f,
                                    default_flow_style=False,
                                    allow_unicode=True,
                                    sort_keys=False,
                                )
                            deleted = True
                    except Exception as e:
                        logger.warning(f"Failed to delete rule from file for site {site_id}: {e}")

            if not deleted:
                return False

            self.reload_site_rules(site_id)
            logger.info(f"Deleted rule {rule_id} from site {site_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete rule from site {site_id}: {e}", exc_info=True)
            return False

    def load_universal_rules_to_site(
        self, site_id: str, universal_rules_file: str = "config/rules_universal.yaml"
    ) -> int:
        """Load only EMS (site-level) rules from file into the site container. Returns count loaded."""
        if not self._container_manager:
            logger.warning("Cannot load universal rules: container manager not available")
            return 0

        try:
            rules_file = Path(universal_rules_file)
            if not rules_file.exists():
                logger.warning(f"Universal rules file not found: {universal_rules_file}")
                return 0

            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = yaml.safe_load(f)
            all_rules = rules_config.get("rules", [])
            if not all_rules:
                return 0

            ems_rules = [
                r for r in all_rules
                if r.get("device_types") and "EMS" in r.get("device_types", [])
            ]
            if not ems_rules:
                return 0

            container = self._container_manager.get_container(site_id, auto_create=True)
            if not container:
                logger.error(f"Failed to get container for site {site_id}")
                return 0

            existing_rules = container.query_rules()
            existing_rule_ids = {r.get("id") for r in existing_rules if r.get("id")}

            loaded_count = 0
            for rule in ems_rules:
                rule_id = rule.get("id")
                if not rule_id:
                    continue
                if rule_id in existing_rule_ids:
                    continue
                if container.write_rule(rule, flush=False):
                    loaded_count += 1

            if loaded_count > 0 and hasattr(container, "flush_rules"):
                try:
                    container.flush_rules()
                except Exception as e:
                    logger.warning(f"Flush rules failed: {e}")

            self.reload_site_rules(site_id)
            logger.info(f"Loaded {loaded_count} universal rules to site {site_id}")
            return loaded_count
        except Exception as e:
            logger.error(f"Failed to load universal rules to site {site_id}: {e}", exc_info=True)
            return 0

    def create_device_rules(self, device_id: str, device_type: str, site_id: str) -> int:
        """Create rules for a device by type. EMS is skipped. Returns count created."""
        if device_type.upper() == "EMS":
            logger.info(f"EMS is site-level only, skipping device-specific rule creation for {device_id}")
            return 0

        if not self._container_manager:
            logger.warning("Cannot create device rules: container manager not available")
            return 0

        try:
            rules_file = Path("config/rules_universal.yaml")
            if not rules_file.exists():
                logger.warning("Universal rules file not found: config/rules_universal.yaml")
                return 0

            with open(rules_file, "r", encoding="utf-8") as f:
                rules_config = yaml.safe_load(f)
            all_rules = rules_config.get("rules", [])
            if not all_rules:
                return 0

            applicable_rules = []
            for rule in all_rules:
                rdt = rule.get("device_types", [])
                if rdt and "EMS" in rdt:
                    continue
                if rdt and device_type.upper() in rdt:
                    device_rule = rule.copy()
                    device_rule["device_ids"] = [device_id]
                    original_id = device_rule.get("id", "")
                    if original_id:
                        if original_id.endswith(f"_{device_id}"):
                            device_rule["id"] = original_id
                        else:
                            parts = original_id.split("_")
                            if len(parts) >= 4 and parts[-1] == device_id:
                                base_id = "_".join(parts[:-1])
                                device_rule["id"] = f"{base_id}_{device_id}"
                            else:
                                device_rule["id"] = f"{original_id}_{device_id}"
                    else:
                        device_rule["id"] = f"rule_{device_id}"
                    applicable_rules.append(device_rule)

            if not applicable_rules:
                return 0

            container = self._container_manager.get_container(site_id, auto_create=True)
            if not container:
                logger.error(f"Failed to get container for site {site_id}")
                return 0

            existing_rules = container.query_rules()
            existing_rule_ids = {rule.get("id") for rule in existing_rules if rule.get("id")}

            created_count = 0
            for rule in applicable_rules:
                rule_id = rule.get("id")
                if not rule_id or rule_id in existing_rule_ids:
                    continue
                if self._postgres_storage:
                    try:
                        self._postgres_storage.save_rule(site_id, rule)
                    except Exception as e:
                        logger.warning(f"Failed to save rule {rule_id} to PostgreSQL: {e}")
                if container.write_rule(rule, flush=False):
                    created_count += 1

            if hasattr(container, "flush_rules"):
                container.flush_rules()

            self.reload_site_rules(site_id)
            logger.info(f"Created {created_count} rules for device {device_id} (type={device_type}) in site {site_id}")
            return created_count
        except Exception as e:
            logger.error(f"Failed to create rules for device {device_id}: {e}", exc_info=True)
            return 0
