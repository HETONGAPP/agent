"""
Rule Engine - Main entry point for rule evaluation and execution
Flexible and extensible rule engine for all energy storage system components
Supports multi-site/datacenter scenarios with site-specific rules and thresholds
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from ..models.device_data import DeviceData
from ..models.alarm import Alarm
from .matcher import RuleMatcher
from .executor import RuleExecutor
from .site_rule_manager import SiteRuleManager

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Main rule engine class
    Flexible rule engine supporting all energy storage system components
    """

    def __init__(
        self,
        rules_file: Optional[str] = None,
        rules: Optional[List[Dict[str, Any]]] = None,
        site_rules_dir: Optional[str] = None,
        enable_multi_site: bool = False,
        site_manager=None,
    ):
        """
        Initialize rule engine

        Args:
            rules_file: Path to global rules YAML file
            rules: Optional list of rule configurations (if not loading from file)
            site_rules_dir: Directory containing site-specific rule files (for multi-site support)
            enable_multi_site: Enable multi-site support with site-specific rules
            site_manager: Optional SiteManager instance for loading rules from database
        """
        self.rules: List[Dict[str, Any]] = []
        self.matcher: Optional[RuleMatcher] = None
        self.executor = RuleExecutor()
        self.enable_multi_site = enable_multi_site
        self.site_rule_manager: Optional[SiteRuleManager] = None

        # Initialize site rule manager if multi-site is enabled
        if enable_multi_site and rules_file:
            self.site_rule_manager = SiteRuleManager(
                global_rules_file=rules_file,
                site_rules_dir=site_rules_dir,
                site_manager=site_manager,  # Pass site_manager for database rule loading
            )
            # Load global rules initially
            self.rules = self.site_rule_manager.get_rules_for_site()
        elif rules_file:
            self.load_rules_from_file(rules_file)
        elif rules:
            self.rules = rules
        else:
            logger.warning("No rules provided, rule engine will be empty")

        if self.rules:
            self.matcher = RuleMatcher(self.rules)

    def load_rules_from_file(self, rules_file: str):
        """
        Load rules from YAML file

        Args:
            rules_file: Path to rules YAML file
        """
        rules_path = Path(rules_file)
        if not rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {rules_file}")

        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            self.rules = config.get("rules", [])
            logger.info(f"Loaded {len(self.rules)} rules from {rules_file}")

            # Reinitialize matcher with new rules
            if self.rules:
                self.matcher = RuleMatcher(self.rules)
        except Exception as e:
            logger.error(f"Failed to load rules from {rules_file}: {e}", exc_info=True)
            raise

    def add_rule(self, rule: Dict[str, Any]):
        """
        Add a rule dynamically

        Args:
            rule: Rule configuration dictionary
        """
        self.rules.append(rule)
        if self.matcher:
            self.matcher.rules = self.rules
        else:
            self.matcher = RuleMatcher(self.rules)
        logger.info(f"Added rule: {rule.get('id', 'UNKNOWN')}")

    def remove_rule(self, rule_id: str):
        """
        Remove a rule by ID

        Args:
            rule_id: Rule ID to remove
        """
        self.rules = [r for r in self.rules if r.get("id") != rule_id]
        if self.matcher:
            self.matcher.rules = self.rules
        logger.info(f"Removed rule: {rule_id}")

    def evaluate(
        self, device_data: DeviceData, history: Optional[List[DeviceData]] = None
    ) -> List[Alarm]:
        """
        Evaluate device data against all rules and generate alarms
        Supports site-specific rules if multi-site is enabled

        Args:
            device_data: Device data to evaluate
            history: Optional historical data for rate_of_change conditions

        Returns:
            List of generated alarms
        """
        # Get site-specific rules if multi-site is enabled
        if self.enable_multi_site and self.site_rule_manager and device_data.site_id:
            site_rules = self.site_rule_manager.get_rules_for_site(device_data.site_id)
            logger.info(
                f"[RuleEngine] Site {device_data.site_id}: Loaded {len(site_rules)} rules "
                f"(device: {device_data.device_id}, type: {device_data.device_type.value})"
            )
            
            # Log SOC high rule details for debugging
            for rule in site_rules:
                if 'soc' in rule.get('name', '').lower() and 'high' in rule.get('name', '').lower():
                    condition = rule.get('condition', {})
                    threshold = condition.get('value')
                    logger.info(
                        f"[RuleEngine] SOC High rule found: {rule.get('id')}, "
                        f"threshold={threshold}, enabled={rule.get('enabled', True)}, "
                        f"device_ids={rule.get('device_ids', [])}"
                    )
            
            # Apply site-specific thresholds
            site_rules = [
                self.site_rule_manager.apply_site_thresholds(rule, device_data.site_id)
                for rule in site_rules
            ]
            
            # Create temporary matcher with site-specific rules
            temp_matcher = RuleMatcher(site_rules)
            matched_rules = temp_matcher.match(device_data, history)
            logger.info(
                f"[RuleEngine] Site {device_data.site_id}: Matched {len(matched_rules)} rules "
                f"(rule_ids: {[r['rule'].get('id') for r in matched_rules]})"
            )
        else:
            if not self.matcher:
                logger.warning("No rules loaded, cannot evaluate")
                return []
            matched_rules = self.matcher.match(device_data, history)

        # Generate alarms
        alarms = []
        for matched_rule in matched_rules:
            try:
                if self.enable_multi_site and self.site_rule_manager and device_data.site_id:
                    alarm = temp_matcher.create_alarm(matched_rule)
                else:
                    alarm = self.matcher.create_alarm(matched_rule)
                logger.info(
                    f"[RuleEngine] Generated alarm: {alarm.alarm_id} "
                    f"(rule_id: {alarm.metadata.get('rule_id')}, "
                    f"alarm_type: {alarm.alarm_type}, severity: {alarm.severity})"
                )
                alarms.append(alarm)
            except Exception as e:
                logger.error(f"Failed to create alarm from matched rule: {e}", exc_info=True)

        return alarms

    def evaluate_and_execute(
        self, device_data: DeviceData, history: Optional[List[DeviceData]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate device data and execute rule actions

        Args:
            device_data: Device data to evaluate
            history: Optional historical data for rate_of_change conditions

        Returns:
            Dictionary with evaluation results and execution results
        """
        alarms = self.evaluate(device_data, history)

        execution_results = {}
        for alarm in alarms:
            # Find the rule that generated this alarm
            rule_id = alarm.metadata.get("rule_id")
            rule = next((r for r in self.rules if r.get("id") == rule_id), None)

            if rule:
                try:
                    results = self.executor.execute(alarm, device_data, rule)
                    execution_results[alarm.alarm_id] = results
                except Exception as e:
                    logger.error(f"Failed to execute actions for alarm {alarm.alarm_id}: {e}", exc_info=True)
                    execution_results[alarm.alarm_id] = {"error": str(e)}

        return {
            "alarms": alarms,
            "execution_results": execution_results,
        }

    def register_action_handler(self, action_name: str, handler: Callable):
        """
        Register custom action handler

        Args:
            action_name: Action name
            handler: Handler function
        """
        self.executor.register_action_handler(action_name, handler)

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all rules"""
        return self.rules.copy()

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get rule by ID"""
        return next((r for r in self.rules if r.get("id") == rule_id), None)

    def get_rules_for_device_type(self, device_type: str) -> List[Dict[str, Any]]:
        """Get rules applicable to device type"""
        return [
            r
            for r in self.rules
            if not r.get("device_types") or device_type in r.get("device_types", [])
        ]

