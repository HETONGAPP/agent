"""
Site-specific rule manager for multi-datacenter support
Supports different rules and thresholds for each site
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class SiteRuleManager:
    """
    Manages site-specific rules and thresholds
    Supports hierarchical rule loading:
    1. Global rules (default)
    2. Site-specific rules (override)
    3. Device-specific rules (override)
    """

    def __init__(self, global_rules_file: str, site_rules_dir: Optional[str] = None, site_manager=None):
        """
        Initialize site rule manager

        Args:
            global_rules_file: Path to global rules file (default rules for all sites)
            site_rules_dir: Directory containing site-specific rule files
                          Format: {site_rules_dir}/{site_id}_rules.yaml
            site_manager: Optional SiteManager instance for loading rules from database
        """
        self.global_rules_file = Path(global_rules_file)
        self.site_rules_dir = Path(site_rules_dir) if site_rules_dir else None
        self.site_manager = site_manager  # For loading rules from database

        # Cache for loaded rules: {site_id: [rules]}
        self.site_rules_cache: Dict[str, List[Dict[str, Any]]] = {}

        # Cache for site configurations: {site_id: {config}}
        self.site_configs: Dict[str, Dict[str, Any]] = {}

        # Load global rules
        self.global_rules = self._load_rules_file(self.global_rules_file)
        logger.debug(f"Loaded {len(self.global_rules)} global rules")

    def _load_rules_file(self, rules_file: Path) -> List[Dict[str, Any]]:
        """Load rules from YAML file"""
        if not rules_file.exists():
            logger.warning(f"Rules file not found: {rules_file}")
            return []

        try:
            with open(rules_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("rules", [])
        except Exception as e:
            logger.error(f"Failed to load rules from {rules_file}: {e}", exc_info=True)
            return []

    def _load_site_rules(self, site_id: str) -> List[Dict[str, Any]]:
        """
        Load site-specific rules
        Priority: Database (via SiteManager) > File
        Global rules are loaded from file, site rules are loaded from database first, then file as fallback
        """
        # Load site rules from SiteManager (which handles database > file priority)
        if self.site_manager:
            try:
                rules = self.site_manager.get_site_rules(site_id)
                return rules
            except Exception as e:
                logger.warning(f"Failed to load rules for site {site_id}: {e}")
                return []
        
        # If site_manager is not available, fallback to file
        if not self.site_rules_dir or not self.site_rules_dir.exists():
            return []

        site_rules_file = self.site_rules_dir / f"{site_id}_rules.yaml"
        if not site_rules_file.exists():
            return []

        rules = self._load_rules_file(site_rules_file)
        return rules

    def _load_site_config(self, site_id: str) -> Dict[str, Any]:
        """Load site configuration (thresholds, etc.)"""
        if not self.site_rules_dir or not self.site_rules_dir.exists():
            return {}

        site_config_file = self.site_rules_dir / f"{site_id}_config.yaml"
        if not site_config_file.exists():
            return {}

        try:
            with open(site_config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(
                f"Failed to load site config for {site_id}: {e}", exc_info=True
            )
            return {}

    def get_rules_for_site(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get rules for a specific site
        Merges site-specific rules with base (global) rules
        Priority: site-specific rules are checked first, then base rules
        If fields overlap, base rules take precedence to avoid duplicate alarms

        Args:
            site_id: Site ID (None for global rules only)

        Returns:
            List of rules for the site (site-specific first, then base rules)
        """
        if not site_id:
            return self.global_rules.copy()

        # Check cache
        if site_id in self.site_rules_cache:
            return self.site_rules_cache[site_id].copy()

        # Load site-specific rules (from database via site_manager)
        site_rules = self._load_site_rules(site_id)

        # Merge rules: site-specific rules first, then base rules
        # If fields overlap, base rules take precedence
        merged_rules = self._merge_rules_with_priority(site_rules, self.global_rules)

        # Cache the result
        self.site_rules_cache[site_id] = merged_rules

        return merged_rules.copy()

    def _merge_rules(
        self, global_rules: List[Dict[str, Any]], site_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge global and site rules (legacy method - kept for backward compatibility)
        Site rules override global rules with the same ID
        """
        # Create a map of global rules by ID
        rules_map = {rule.get("id"): rule.copy() for rule in global_rules}

        # Override with site rules
        for site_rule in site_rules:
            rule_id = site_rule.get("id")
            if rule_id:
                rules_map[rule_id] = site_rule.copy()
            else:
                # Add new rule without ID
                rules_map[f"site_rule_{len(rules_map)}"] = site_rule.copy()

        return list(rules_map.values())

    def _merge_rules_with_priority(
        self, site_rules: List[Dict[str, Any]], base_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge site-specific rules with base rules
        Priority: site-specific rules take precedence over base rules
        If rule IDs overlap, site rules override base rules with the same ID
        Also check for device-specific rule IDs (e.g., RULE_BMS_006_BMS_001 vs RULE_BMS_006)
        
        Args:
            site_rules: Site-specific rules (checked first, take precedence)
            base_rules: Base/global rules (checked second)
            
        Returns:
            Merged rules list: site-specific rules first, then filtered base rules
        """
        # Create a map of site rules by ID for quick lookup
        site_rules_by_id = {rule.get("id"): rule for rule in site_rules if rule.get("id")}
        
        # Track which rule IDs exist in site rules
        site_rule_ids = set(site_rules_by_id.keys())
        
        # Also track base rule IDs that match device-specific site rules
        # e.g., if site has RULE_BMS_006_BMS_001, we should skip base RULE_BMS_006
        base_rule_ids_to_skip = set()
        for site_rule_id in site_rule_ids:
            # Check if site rule ID is device-specific (contains device ID suffix)
            # Pattern: RULE_{TYPE}_{NUM}_{DEVICE_ID}
            parts = site_rule_id.split("_")
            if len(parts) >= 4:  # At least RULE_TYPE_NUM_DEVICE
                # Extract base rule ID (e.g., RULE_BMS_006 from RULE_BMS_006_BMS_001)
                base_rule_id = "_".join(parts[:3])  # RULE_TYPE_NUM
                base_rule_ids_to_skip.add(base_rule_id)
                logger.debug(
                    f"Site rule {site_rule_id} is device-specific, will skip base rule {base_rule_id}"
                )
        
        # Filter base rules: exclude rules with IDs that exist in site rules or match device-specific patterns
        filtered_base_rules = []
        for base_rule in base_rules:
            base_rule_id = base_rule.get("id")
            if not base_rule_id:
                # Keep rules without IDs
                filtered_base_rules.append(base_rule)
                continue
            
            # Skip if exact ID match
            if base_rule_id in site_rule_ids:
                logger.debug(
                    f"Skipping base rule {base_rule_id} due to exact ID match with site rule"
                )
                continue
            
            # Skip if base rule ID matches a device-specific site rule pattern
            if base_rule_id in base_rule_ids_to_skip:
                logger.debug(
                    f"Skipping base rule {base_rule_id} due to device-specific site rule override"
                )
                continue
            
            filtered_base_rules.append(base_rule)
        
        # Return: site-specific rules first, then filtered base rules
        # This ensures site rules are checked first and can override base rules
        merged = site_rules.copy() + filtered_base_rules
        logger.debug(
            f"Merged {len(site_rules)} site rules with {len(filtered_base_rules)} base rules "
            f"(total: {len(merged)} rules, skipped {len(base_rules) - len(filtered_base_rules)} base rules)"
        )
        return merged

    def get_site_config(self, site_id: str) -> Dict[str, Any]:
        """
        Get site-specific configuration (thresholds, etc.)

        Args:
            site_id: Site ID

        Returns:
            Site configuration dictionary
        """
        if site_id not in self.site_configs:
            self.site_configs[site_id] = self._load_site_config(site_id)

        return self.site_configs[site_id].copy()

    def apply_site_thresholds(
        self, rule: Dict[str, Any], site_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply site-specific thresholds to a rule

        Args:
            rule: Rule dictionary
            site_id: Site ID

        Returns:
            Rule with site-specific thresholds applied
        """
        if not site_id:
            return rule.copy()

        site_config = self.get_site_config(site_id)
        if not site_config:
            return rule.copy()

        # Get threshold overrides for this rule
        rule_id = rule.get("id")
        threshold_overrides = site_config.get("threshold_overrides", {}).get(
            rule_id, {}
        )

        if not threshold_overrides:
            return rule.copy()

        # Create a copy of the rule
        updated_rule = rule.copy()

        # Override condition value if specified
        if "condition" in updated_rule and "value" in threshold_overrides:
            updated_rule["condition"] = updated_rule["condition"].copy()
            updated_rule["condition"]["value"] = threshold_overrides["value"]

        # Override severity if specified
        if "severity" in threshold_overrides:
            updated_rule["severity"] = threshold_overrides["severity"]

        # Override priority if specified
        if "priority" in threshold_overrides:
            updated_rule["priority"] = threshold_overrides["priority"]

        logger.debug(f"Applied site thresholds for rule {rule_id} on site {site_id}")

        return updated_rule

    def reload_site_rules(self, site_id: Optional[str] = None):
        """
        Reload rules for a specific site or all sites
        Also clears SiteManager cache to ensure fresh data is loaded from database

        Args:
            site_id: Site ID (None to reload all)
        """
        if site_id:
            # Clear rule engine cache first
            if site_id in self.site_rules_cache:
                del self.site_rules_cache[site_id]
            if site_id in self.site_configs:
                del self.site_configs[site_id]
            # Clear site manager cache to ensure database is queried fresh
            if self.site_manager and hasattr(self.site_manager, 'clear_site_rules_cache'):
                self.site_manager.clear_site_rules_cache(site_id)
            logger.info(f"Reloaded rules for site {site_id}")
        else:
            self.site_rules_cache.clear()
            self.site_configs.clear()
            if self.site_manager and hasattr(self.site_manager, 'clear_site_rules_cache'):
                self.site_manager.clear_site_rules_cache(None)
            self.global_rules = self._load_rules_file(self.global_rules_file)

    def get_all_site_ids(self) -> List[str]:
        """Get list of all configured site IDs"""
        if not self.site_rules_dir or not self.site_rules_dir.exists():
            return []

        site_ids = []
        for file in self.site_rules_dir.glob("*_rules.yaml"):
            site_id = file.stem.replace("_rules", "")
            site_ids.append(site_id)

        return site_ids
