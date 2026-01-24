"""
Condition evaluation for rule engine
Supports various condition types: threshold, status, rate_of_change, etc.
"""

from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from ..models.device_data import DeviceData


class ConditionType(str, Enum):
    """Condition type enumeration"""

    THRESHOLD = "threshold"  # Simple threshold comparison
    STATUS = "status"  # Status string comparison
    RATE_OF_CHANGE = "rate_of_change"  # Rate of change over time
    RANGE = "range"  # Value within/outside range
    COMBINATION = "combination"  # AND/OR combination of conditions
    CUSTOM = "custom"  # Custom condition function


class ConditionEvaluator:
    """Evaluate conditions against device data"""

    @staticmethod
    def evaluate(
        condition: Dict[str, Any], device_data: DeviceData, history: Optional[list] = None
    ) -> bool:
        """
        Evaluate condition against device data

        Args:
            condition: Condition configuration dict
            device_data: Device data to evaluate
            history: Optional historical data for rate_of_change conditions

        Returns:
            True if condition matches, False otherwise
        """
        condition_type = condition.get("type", ConditionType.THRESHOLD.value)

        if condition_type == ConditionType.THRESHOLD.value:
            return ConditionEvaluator._evaluate_threshold(condition, device_data)
        elif condition_type == ConditionType.STATUS.value:
            return ConditionEvaluator._evaluate_status(condition, device_data)
        elif condition_type == ConditionType.RATE_OF_CHANGE.value:
            return ConditionEvaluator._evaluate_rate_of_change(condition, device_data, history)
        elif condition_type == ConditionType.RANGE.value:
            return ConditionEvaluator._evaluate_range(condition, device_data)
        elif condition_type == ConditionType.COMBINATION.value:
            return ConditionEvaluator._evaluate_combination(condition, device_data, history)
        else:
            # Unknown condition type, return False
            return False

    @staticmethod
    def _evaluate_threshold(condition: Dict[str, Any], device_data: DeviceData) -> bool:
        """Evaluate threshold condition"""
        import logging
        logger = logging.getLogger(__name__)
        
        field_path = condition.get("field")
        operator = condition.get("operator", ">")
        threshold_value = condition.get("value")

        if field_path is None or threshold_value is None:
            logger.debug(f"[ConditionEvaluator] Missing field_path or threshold_value: field={field_path}, threshold={threshold_value}")
            return False

        field_value = device_data.get_field(field_path)
        if field_value is None:
            logger.debug(f"[ConditionEvaluator] Field '{field_path}' not found in device data. Available fields: {list(device_data.data.keys())}")
            return False

        try:
            field_value = float(field_value)
            threshold_value = float(threshold_value)
        except (ValueError, TypeError) as e:
            logger.debug(f"[ConditionEvaluator] Cannot convert to float: field_value={field_value}, threshold={threshold_value}, error={e}")
            return False

        # Evaluate condition
        result = False
        if operator == ">":
            result = field_value > threshold_value
        elif operator == ">=":
            result = field_value >= threshold_value
        elif operator == "<":
            result = field_value < threshold_value
        elif operator == "<=":
            result = field_value <= threshold_value
        elif operator == "==":
            result = abs(field_value - threshold_value) < 0.0001  # Float comparison
        elif operator == "!=":
            result = abs(field_value - threshold_value) >= 0.0001
        else:
            logger.warning(f"[ConditionEvaluator] Unknown operator: {operator}")
            return False
        
        logger.debug(
            f"[ConditionEvaluator] Threshold evaluation: {field_path} {operator} {threshold_value} "
            f"-> {field_value} {operator} {threshold_value} = {result}"
        )
        
        return result

    @staticmethod
    def _evaluate_status(condition: Dict[str, Any], device_data: DeviceData) -> bool:
        """Evaluate status condition"""
        field_path = condition.get("field")
        operator = condition.get("operator", "==")
        expected_value = condition.get("value")

        if field_path is None or expected_value is None:
            return False

        field_value = device_data.get_field(field_path)
        if field_value is None:
            return False

        # Convert to string for comparison
        field_value = str(field_value).lower()
        expected_value = str(expected_value).lower()

        if operator == "==":
            return field_value == expected_value
        elif operator == "!=":
            return field_value != expected_value
        elif operator == "in":
            # Check if field_value is in expected_value (list)
            if isinstance(expected_value, list):
                return field_value in [str(v).lower() for v in expected_value]
            return False
        elif operator == "not_in":
            if isinstance(expected_value, list):
                return field_value not in [str(v).lower() for v in expected_value]
            return True
        else:
            return False

    @staticmethod
    def _evaluate_rate_of_change(
        condition: Dict[str, Any], device_data: DeviceData, history: Optional[list] = None
    ) -> bool:
        """Evaluate rate of change condition"""
        field_path = condition.get("field")
        operator = condition.get("operator", ">")
        threshold_rate = condition.get("value")
        time_window = condition.get("time_window", 60)  # seconds

        if field_path is None or threshold_rate is None or history is None:
            return False

        # Get current value
        current_value = device_data.get_field(field_path)
        if current_value is None:
            return False

        try:
            current_value = float(current_value)
            threshold_rate = float(threshold_rate)
        except (ValueError, TypeError):
            return False

        # Find historical value within time window
        current_time = device_data.timestamp
        window_start = current_time - timedelta(seconds=time_window)

        historical_value = None
        historical_time = None

        for hist_data in reversed(history):  # Start from most recent
            if isinstance(hist_data, DeviceData):
                if hist_data.timestamp < window_start:
                    break
                value = hist_data.get_field(field_path)
                if value is not None:
                    try:
                        historical_value = float(value)
                        historical_time = hist_data.timestamp
                        break
                    except (ValueError, TypeError):
                        continue

        if historical_value is None or historical_time is None:
            return False

        # Calculate rate of change
        time_diff = (current_time - historical_time).total_seconds()
        if time_diff <= 0:
            return False

        rate = (current_value - historical_value) / time_diff

        # Compare with threshold
        if operator == ">":
            return rate > threshold_rate
        elif operator == ">=":
            return rate >= threshold_rate
        elif operator == "<":
            return rate < threshold_rate
        elif operator == "<=":
            return rate <= threshold_rate
        else:
            return False

    @staticmethod
    def _evaluate_range(condition: Dict[str, Any], device_data: DeviceData) -> bool:
        """Evaluate range condition"""
        field_path = condition.get("field")
        min_value = condition.get("min")
        max_value = condition.get("max")
        inclusive = condition.get("inclusive", True)

        if field_path is None:
            return False

        field_value = device_data.get_field(field_path)
        if field_value is None:
            return False

        try:
            field_value = float(field_value)
        except (ValueError, TypeError):
            return False

        if min_value is not None:
            min_value = float(min_value)
            if inclusive:
                if field_value < min_value:
                    return False
            else:
                if field_value <= min_value:
                    return False

        if max_value is not None:
            max_value = float(max_value)
            if inclusive:
                if field_value > max_value:
                    return False
            else:
                if field_value >= max_value:
                    return False

        return True

    @staticmethod
    def _evaluate_combination(
        condition: Dict[str, Any], device_data: DeviceData, history: Optional[list] = None
    ) -> bool:
        """Evaluate combination condition (AND/OR)"""
        logic = condition.get("logic", "AND").upper()
        conditions = condition.get("conditions", [])

        if not conditions:
            return False

        results = []
        for sub_condition in conditions:
            result = ConditionEvaluator.evaluate(sub_condition, device_data, history)
            results.append(result)

        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        else:
            return False

