"""
Rule matcher for matching rules against device data
Supports flexible matching for all device types
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, UTC

from ..models.device_data import DeviceData, DeviceType
from ..models.alarm import Alarm, AlarmSeverity, AlarmLevel
from .conditions import ConditionEvaluator

logger = logging.getLogger(__name__)


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
            rule_id = rule.get('id', 'UNKNOWN')
            if self._is_rule_applicable(rule, device_data):
                if self._evaluate_rule(rule, device_data, history):
                    matched_rules.append({
                        "rule": rule,
                        "device_data": device_data,
                        "matched_at": datetime.now(UTC),
                    })
                    logger.info(
                        f"[RuleMatcher] ✓ Rule {rule_id} matched for device {device_data.device_id} "
                        f"(type: {device_data.device_type.value}, site: {device_data.site_id}, rule_name={rule.get('name')})"
                    )
                else:
                    # Log why rule didn't match (condition evaluation failed)
                    condition = rule.get("condition", {})
                    field_path = condition.get("field")
                    if field_path:
                        field_value = device_data.get_field(field_path)
                        logger.info(
                            f"[RuleMatcher] Rule {rule_id} condition not met: "
                            f"{field_path}={field_value}, condition: {condition.get('operator')} {condition.get('value')} "
                            f"(device_id={device_data.device_id}, site_id={device_data.site_id})"
                        )
            else:
                # Log why rule is not applicable
                rule_device_ids = rule.get("device_ids", [])
                rule_device_types = rule.get("device_types", [])
                logger.debug(
                    f"[RuleMatcher] Rule {rule_id} not applicable: "
                    f"device_id={device_data.device_id} (rule requires: {rule_device_ids}), "
                    f"device_type={device_data.device_type.value} (rule requires: {rule_device_types})"
                )

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
            logger.debug(
                f"[RuleMatcher] Rule {rule.get('id')} not applicable: device_id={device_data.device_id} "
                f"not in rule's device_ids={rule_device_ids}"
            )
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

        # Generate alarm ID with consistent format
        # Format: RULE_{BASE_RULE_ID}_{DEVICE_ID}_{TIMESTAMP}
        # Example: RULE_BMS_001_BMS_001_1769297380
        # 
        # Logic:
        # 1. Extract base rule ID (remove device_id suffix if present)
        # 2. Ensure RULE_ prefix exists
        # 3. Always append device_id and timestamp
        
        original_rule_id = rule.get('id', 'UNKNOWN')
        device_id = device_data.device_id
        timestamp = int(device_data.timestamp.timestamp())
        
        # Step 1: Validate and normalize rule_id
        if not original_rule_id or original_rule_id == 'UNKNOWN':
            logger.warning(f"Invalid rule_id: {original_rule_id}, using fallback")
            base_rule_id = 'RULE_UNKNOWN'
        else:
            # Step 2: Extract base rule ID (remove device_id suffix if present)
            # Handle cases like:
            # - "RULE_BMS_001_BMS_001" -> "RULE_BMS_001"
            # - "RULE_BMS_001" -> "RULE_BMS_001"
            # - "BMS_001" -> "RULE_BMS_001"
            temp_rule_id = original_rule_id
            
            # Remove device_id suffix if present
            if temp_rule_id.endswith(f"_{device_id}"):
                # Extract base: remove the last part (device_id)
                parts = temp_rule_id.split("_")
                if len(parts) > 1:
                    temp_rule_id = "_".join(parts[:-1])
                    logger.debug(f"Extracted base rule ID: {original_rule_id} -> {temp_rule_id}")
            
            # Step 3: Ensure RULE_ prefix exists
            if not temp_rule_id.startswith('RULE_'):
                base_rule_id = f"RULE_{temp_rule_id}"
                logger.debug(f"Added RULE_ prefix: {temp_rule_id} -> {base_rule_id}")
            else:
                base_rule_id = temp_rule_id
        
        # Step 4: Generate alarm ID: RULE_{BASE_RULE_ID}_{DEVICE_ID}_{TIMESTAMP}
        alarm_id = f"{base_rule_id}_{device_id}_{timestamp}"
        
        # Log for debugging
        logger.info(
            f"Generated alarm_id: {alarm_id} "
            f"(original_rule_id: {original_rule_id}, base_rule_id: {base_rule_id}, "
            f"device_id: {device_id}, timestamp: {timestamp})"
        )

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

