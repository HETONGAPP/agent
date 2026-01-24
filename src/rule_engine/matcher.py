"""
Rule matcher for matching rules against device data
Supports flexible matching for all device types
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, UTC

from ..models.device_data import DeviceData, DeviceType
from ..models.alarm import Alarm, AlarmSeverity, AlarmLevel
from .conditions import ConditionEvaluator


class RuleMatcher:
    """Match rules against device data"""

    def __init__(self, rules: List[Dict[str, Any]]):
        """
        Initialize rule matcher

        Args:
            rules: List of rule configurations
        """
        self.rules = rules
        self._device_type_cache: Dict[str, List[Dict[str, Any]]] = {}

    def match(self, device_data: DeviceData, history: Optional[List[DeviceData]] = None) -> List[Dict[str, Any]]:
        """
        Match rules against device data

        Args:
            device_data: Device data to match against
            history: Optional historical data for rate_of_change conditions

        Returns:
            List of matched rules with context
        """
        matched_rules = []

        # Filter rules by device type if specified
        applicable_rules = self._get_applicable_rules(device_data.device_type)

        for rule in applicable_rules:
            if self._is_rule_applicable(rule, device_data):
                if self._evaluate_rule(rule, device_data, history):
                    matched_rules.append({
                        "rule": rule,
                        "device_data": device_data,
                        "matched_at": datetime.now(UTC),
                    })

        # Sort by priority (higher priority first)
        matched_rules.sort(key=lambda x: x["rule"].get("priority", 0), reverse=True)

        return matched_rules

    def _get_applicable_rules(self, device_type: DeviceType) -> List[Dict[str, Any]]:
        """
        Get rules applicable to device type
        
        Includes:
        - Rules that match the device type
        - EMS (GLOBAL) rules (device_types contains "EMS") - these match all device types
        """
        cache_key = device_type.value
        if cache_key in self._device_type_cache:
            return self._device_type_cache[cache_key]

        applicable = []
        for rule in self.rules:
            rule_device_types = rule.get("device_types", [])
            # Include rule if:
            # 1. Rule has no device_types (applies to all)
            # 2. Rule's device_types includes this device type
            # 3. Rule is an EMS rule (device_types contains "EMS") - EMS rules match all device types
            if not rule_device_types or device_type.value in rule_device_types or "EMS" in rule_device_types:
                applicable.append(rule)

        self._device_type_cache[cache_key] = applicable
        return applicable

    def _is_rule_applicable(self, rule: Dict[str, Any], device_data: DeviceData) -> bool:
        """
        Check if rule is applicable to device data
        
        Rules are matched based on:
        1. Rule must be enabled (enabled != False)
        2. Site ID: Rules are already filtered by site_id in RuleEngine.evaluate()
        3. Device Type: Rule's device_types must include device's type (except EMS rules)
        4. Device ID: If rule has device_ids, device must be in the list (empty device_ids = all devices)
        5. EMS (GLOBAL) rules: Match all devices in the site (device_types contains "EMS")
        """
        # Check if rule is enabled (default to True if not specified)
        rule_enabled = rule.get("enabled")
        if rule_enabled is False:
            return False
        
        rule_device_types = rule.get("device_types", [])
        rule_device_ids = rule.get("device_ids", [])
        
        # EMS (GLOBAL) rules: Match all devices in the site
        # EMS rules have device_types=["EMS"] and should match all device types
        is_ems_rule = rule_device_types and "EMS" in rule_device_types
        
        if is_ems_rule:
            # EMS rules match all devices in the site (site_id already filtered in RuleEngine)
            # But still check device_ids if specified
            if rule_device_ids and device_data.device_id not in rule_device_ids:
                return False
        else:
            # Non-EMS rules: Check device type filter
            if rule_device_types and device_data.device_type.value not in rule_device_types:
                return False

        # Check device ID filter
        if rule_device_ids and device_data.device_id not in rule_device_ids:
            return False

        # Check source filter
        rule_sources = rule.get("sources", [])
        if rule_sources and device_data.source not in rule_sources:
            return False

        # Check if required fields exist
        condition = rule.get("condition", {})
        field_path = condition.get("field")
        if field_path and not device_data.has_field(field_path):
            return False

        return True

    def _evaluate_rule(
        self, rule: Dict[str, Any], device_data: DeviceData, history: Optional[List[DeviceData]] = None
    ) -> bool:
        """Evaluate if rule condition matches"""
        condition = rule.get("condition", {})
        if not condition:
            return False

        return ConditionEvaluator.evaluate(condition, device_data, history)

    def create_alarm(self, matched_rule: Dict[str, Any]) -> Alarm:
        """
        Create Alarm object from matched rule

        Args:
            matched_rule: Matched rule context from match() method

        Returns:
            Alarm object
        """
        rule = matched_rule["rule"]
        device_data = matched_rule["device_data"]

        # Map severity string to AlarmSeverity enum
        severity_str = rule.get("severity", "Warning")
        try:
            severity = AlarmSeverity(severity_str)
        except ValueError:
            severity = AlarmSeverity.WARNING

        # Generate alarm ID
        alarm_id = f"{rule.get('id', 'UNKNOWN')}_{device_data.device_id}_{int(device_data.timestamp.timestamp())}"

        # Build metadata
        metadata = {
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "device_id": device_data.device_id,
            "device_type": device_data.device_type.value,
            "source": device_data.source,
            "priority": rule.get("priority", 0),
        }

        # Add rule metadata
        rule_metadata = rule.get("metadata", {})
        if rule_metadata:
            metadata.update(rule_metadata)

        # Add device data snapshot
        metadata["device_data_snapshot"] = device_data.to_dict()

        # Determine alarm level based on rule metadata or default to device level
        alarm_level_str = rule.get("metadata", {}).get("alarm_level", "device_level")
        try:
            alarm_level = AlarmLevel(alarm_level_str)
        except ValueError:
            # Default to device level for unknown values
            alarm_level = AlarmLevel.DEVICE

        return Alarm(
            alarm_id=alarm_id,
            alarm_type=rule.get("metadata", {}).get("alarm_type", rule.get("name", "Unknown")),
            severity=severity,
            timestamp=matched_rule.get("matched_at", device_data.timestamp),
            source=device_data.source,
            alarm_level=alarm_level,
            metadata=metadata,
        )

