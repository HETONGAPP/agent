"""
Rule Conflict Detector
Detects conflicts between rules to prevent overlapping or contradictory rules
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of rule conflicts"""
    ID_DUPLICATE = "id_duplicate"  # Same rule ID
    CONDITION_OVERLAP = "condition_overlap"  # Conditions may match same data
    LOGICAL_CONTRADICTION = "logical_contradiction"  # Conditions contradict each other
    DEVICE_OVERLAP = "device_overlap"  # Same device scope
    PRIORITY_CONFLICT = "priority_conflict"  # Same priority but different outcomes
    FIELD_CONFLICT = "field_conflict"  # Same field but different thresholds
    ALARM_TYPE_DUPLICATE = "alarm_type_duplicate"  # Same alarm_type


class RuleConflictDetector:
    """Detect conflicts between rules"""

    @staticmethod
    def detect_conflicts(
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
        strict_mode: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts between a new rule and existing rules

        Args:
            new_rule: The new rule to check
            existing_rules: List of existing rules to check against
            strict_mode: If True, report all potential conflicts. If False, only report critical conflicts.

        Returns:
            List of conflict dictionaries with type, severity, and description
        """
        conflicts = []

        new_rule_id = new_rule.get("id")
        if not new_rule_id:
            conflicts.append({
                "type": "invalid",
                "severity": "error",
                "message": "Rule ID is required",
                "rule_id": None
            })
            return conflicts

        # Check for duplicate ID
        for existing_rule in existing_rules:
            existing_rule_id = existing_rule.get("id")
            if existing_rule_id == new_rule_id:
                conflicts.append({
                    "type": ConflictType.ID_DUPLICATE,
                    "severity": "error",
                    "message": f"Rule ID '{new_rule_id}' already exists",
                    "rule_id": existing_rule_id,
                    "conflicting_rule_id": existing_rule_id
                })
                return conflicts  # ID conflict is critical, return immediately

        # Check for conflicts with existing rules
        for existing_rule in existing_rules:
            rule_conflicts = RuleConflictDetector._check_rule_pair_conflict(
                new_rule, existing_rule, strict_mode
            )
            conflicts.extend(rule_conflicts)

        return conflicts

    @staticmethod
    def _check_rule_pair_conflict(
        rule1: Dict[str, Any],
        rule2: Dict[str, Any],
        strict_mode: bool
    ) -> List[Dict[str, Any]]:
        """Check for conflicts between two rules"""
        conflicts = []

        # Check device scope overlap
        device_conflict = RuleConflictDetector._check_device_overlap(rule1, rule2)
        if device_conflict:
            conflicts.append(device_conflict)

        # If rules don't apply to same devices, no further conflict checking needed
        if not device_conflict:
            return conflicts

        # Check condition conflicts
        condition_conflicts = RuleConflictDetector._check_condition_conflicts(
            rule1, rule2, strict_mode
        )
        conflicts.extend(condition_conflicts)

        # Check alarm_type duplicate
        alarm_type_conflict = RuleConflictDetector._check_alarm_type_duplicate(rule1, rule2)
        if alarm_type_conflict:
            conflicts.append(alarm_type_conflict)

        # Check priority conflicts
        priority_conflict = RuleConflictDetector._check_priority_conflict(rule1, rule2)
        if priority_conflict:
            conflicts.append(priority_conflict)

        return conflicts

    @staticmethod
    def _check_device_overlap(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if two rules apply to overlapping device scopes"""
        rule1_device_types = set(rule1.get("device_types", []))
        rule2_device_types = set(rule2.get("device_types", []))

        rule1_device_ids = set(rule1.get("device_ids", []))
        rule2_device_ids = set(rule2.get("device_ids", []))

        # If both rules have no device_types, they apply to all devices (overlap)
        if not rule1_device_types and not rule2_device_types:
            return {
                "type": ConflictType.DEVICE_OVERLAP,
                "severity": "warning",
                "message": "Both rules apply to all device types",
                "rule_id": rule1.get("id"),
                "conflicting_rule_id": rule2.get("id")
            }

        # Check device type overlap
        type_overlap = rule1_device_types & rule2_device_types
        if not type_overlap and (rule1_device_types or rule2_device_types):
            # No device type overlap
            return None

        # If both rules have device_ids, check for overlap
        if rule1_device_ids and rule2_device_ids:
            id_overlap = rule1_device_ids & rule2_device_ids
            if not id_overlap:
                # Same device types but different device IDs - no conflict
                return None

        # Device scope overlaps
        return {
            "type": ConflictType.DEVICE_OVERLAP,
            "severity": "warning",
            "message": f"Rules apply to overlapping device scope (types: {type_overlap}, "
                      f"device_ids: {rule1_device_ids & rule2_device_ids if rule1_device_ids and rule2_device_ids else 'all'})",
            "rule_id": rule1.get("id"),
            "conflicting_rule_id": rule2.get("id")
        }

    @staticmethod
    def _check_condition_conflicts(
        rule1: Dict[str, Any],
        rule2: Dict[str, Any],
        strict_mode: bool
    ) -> List[Dict[str, Any]]:
        """Check for condition conflicts between two rules"""
        conflicts = []

        condition1 = rule1.get("condition", {})
        condition2 = rule2.get("condition", {})

        # Check if conditions monitor the same field
        field1 = condition1.get("field")
        field2 = condition2.get("field")

        if not field1 or not field2 or field1 != field2:
            # Different fields - no conflict
            return conflicts

        # Same field - check for logical conflicts
        type1 = condition1.get("type", "threshold")
        type2 = condition2.get("type", "threshold")

        if type1 != type2:
            # Different condition types on same field - potential conflict
            if strict_mode:
                conflicts.append({
                    "type": ConflictType.CONDITION_OVERLAP,
                    "severity": "warning",
                    "message": f"Rules monitor same field '{field1}' with different condition types "
                              f"({type1} vs {type2})",
                    "rule_id": rule1.get("id"),
                    "conflicting_rule_id": rule2.get("id")
                })
            return conflicts

        # Same field and condition type - check for threshold conflicts
        if type1 == "threshold":
            conflict = RuleConflictDetector._check_threshold_conflict(condition1, condition2)
            if conflict:
                conflict["rule_id"] = rule1.get("id")
                conflict["conflicting_rule_id"] = rule2.get("id")
                conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _check_threshold_conflict(
        condition1: Dict[str, Any],
        condition2: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for threshold conflicts"""
        field1 = condition1.get("field")
        field2 = condition2.get("field")

        if field1 != field2:
            return None

        op1 = condition1.get("operator", ">")
        val1 = condition1.get("value")
        op2 = condition2.get("operator", ">")
        val2 = condition2.get("value")

        try:
            val1 = float(val1)
            val2 = float(val2)
        except (TypeError, ValueError):
            return None

        # Check for logical contradiction
        # Example: rule1: field > 50, rule2: field < 50 (contradiction)
        # Example: rule1: field > 50, rule2: field > 60 (overlap but not contradiction)
        # Example: rule1: field > 50, rule2: field < 40 (no overlap)

        contradiction = False
        overlap = False

        # Define ranges for each condition
        range1 = RuleConflictDetector._get_threshold_range(op1, val1)
        range2 = RuleConflictDetector._get_threshold_range(op2, val2)

        if range1 and range2:
            # Check if ranges overlap
            overlap = RuleConflictDetector._ranges_overlap(range1, range2)

            # Check for contradiction (both cannot be true at the same time)
            # This happens when the ranges don't overlap but both could match
            # For example: > 50 and < 50 (contradiction)
            if not overlap:
                if (op1 in [">", ">="] and op2 in ["<", "<="] and val1 <= val2) or \
                   (op1 in ["<", "<="] and op2 in [">", ">="] and val1 >= val2):
                    contradiction = True

        if contradiction:
            return {
                "type": ConflictType.LOGICAL_CONTRADICTION,
                "severity": "error",
                "message": f"Contradictory conditions on field '{field1}': "
                          f"{field1} {op1} {val1} vs {field1} {op2} {val2}",
            }
        elif overlap:
            return {
                "type": ConflictType.CONDITION_OVERLAP,
                "severity": "warning",
                "message": f"Overlapping conditions on field '{field1}': "
                          f"{field1} {op1} {val1} vs {field1} {op2} {val2}",
            }

        return None

    @staticmethod
    def _get_threshold_range(operator: str, value: float) -> Optional[Tuple[float, float, bool, bool]]:
        """
        Get the range that a threshold condition matches
        Returns: (min, max, min_inclusive, max_inclusive) or None
        """
        if operator == ">":
            return (value, float('inf'), False, False)
        elif operator == ">=":
            return (value, float('inf'), True, False)
        elif operator == "<":
            return (float('-inf'), value, False, False)
        elif operator == "<=":
            return (float('-inf'), value, False, True)
        elif operator == "==":
            return (value, value, True, True)
        elif operator == "!=":
            # != matches everything except the value
            return None  # Can't represent as a simple range
        return None

    @staticmethod
    def _ranges_overlap(
        range1: Tuple[float, float, bool, bool],
        range2: Tuple[float, float, bool, bool]
    ) -> bool:
        """Check if two ranges overlap"""
        min1, max1, min1_inc, max1_inc = range1
        min2, max2, min2_inc, max2_inc = range2

        # Check if ranges overlap
        if max1 < min2 or (max1 == min2 and not (max1_inc and min2_inc)):
            return False
        if max2 < min1 or (max2 == min1 and not (max2_inc and min1_inc)):
            return False

        return True

    @staticmethod
    def _check_alarm_type_duplicate(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if two rules have the same alarm_type"""
        alarm_type1 = rule1.get("metadata", {}).get("alarm_type")
        alarm_type2 = rule2.get("metadata", {}).get("alarm_type")

        if alarm_type1 and alarm_type2 and alarm_type1 == alarm_type2:
            return {
                "type": ConflictType.ALARM_TYPE_DUPLICATE,
                "severity": "warning",
                "message": f"Both rules have the same alarm_type '{alarm_type1}'. "
                          f"This may cause duplicate alarms.",
                "rule_id": rule1.get("id"),
                "conflicting_rule_id": rule2.get("id")
            }

        return None

    @staticmethod
    def _check_priority_conflict(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for priority conflicts"""
        priority1 = rule1.get("priority", 0)
        priority2 = rule2.get("priority", 0)

        # If priorities are the same and rules may conflict, warn
        if priority1 == priority2:
            # Check if they have different severities or actions
            severity1 = rule1.get("severity")
            severity2 = rule2.get("severity")
            actions1 = set(rule1.get("actions", []))
            actions2 = set(rule2.get("actions", []))

            if severity1 != severity2 or actions1 != actions2:
                return {
                    "type": ConflictType.PRIORITY_CONFLICT,
                    "severity": "warning",
                    "message": f"Rules have same priority ({priority1}) but different "
                              f"severities ({severity1} vs {severity2}) or actions. "
                              f"Rule matching order may be unpredictable.",
                    "rule_id": rule1.get("id"),
                    "conflicting_rule_id": rule2.get("id")
                }

        return None

    @staticmethod
    def format_conflicts(conflicts: List[Dict[str, Any]]) -> str:
        """Format conflicts into a human-readable message"""
        if not conflicts:
            return "No conflicts detected"

        error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
        warning_conflicts = [c for c in conflicts if c.get("severity") == "warning"]

        messages = []

        if error_conflicts:
            messages.append("ERRORS (must be resolved):")
            for conflict in error_conflicts:
                messages.append(f"  - {conflict.get('message')}")

        if warning_conflicts:
            messages.append("WARNINGS (should be reviewed):")
            for conflict in warning_conflicts:
                messages.append(f"  - {conflict.get('message')}")

        return "\n".join(messages)
