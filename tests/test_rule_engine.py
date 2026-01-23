"""
Tests for rule engine
"""

import pytest
from datetime import datetime

from src.models.device_data import DeviceData, DeviceType, PCSData, UPSData, TMSData
from src.models.bms_data import BMSData
from src.rule_engine import RuleEngine, RuleMatcher, RuleExecutor
from src.rule_engine.conditions import ConditionEvaluator


class TestConditionEvaluator:
    """Test condition evaluator"""

    def test_threshold_condition(self):
        """Test threshold condition"""
        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"max_delta_v": 0.15, "max_temperature": 50.0},
        )

        # Test >= operator
        condition = {
            "type": "threshold",
            "field": "max_delta_v",
            "operator": ">=",
            "value": 0.1,
        }
        assert ConditionEvaluator.evaluate(condition, device_data) is True

        # Test < operator
        condition = {
            "type": "threshold",
            "field": "max_temperature",
            "operator": "<",
            "value": 60.0,
        }
        assert ConditionEvaluator.evaluate(condition, device_data) is True

    def test_status_condition(self):
        """Test status condition"""
        device_data = DeviceData(
            device_id="PCS_001",
            device_type=DeviceType.PCS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"status": "fault", "grid_connection_status": "disconnected"},
        )

        condition = {
            "type": "status",
            "field": "status",
            "operator": "==",
            "value": "fault",
        }
        assert ConditionEvaluator.evaluate(condition, device_data) is True

        condition = {
            "type": "status",
            "field": "grid_connection_status",
            "operator": "==",
            "value": "disconnected",
        }
        assert ConditionEvaluator.evaluate(condition, device_data) is True


class TestRuleMatcher:
    """Test rule matcher"""

    def test_match_bms_rule(self):
        """Test matching BMS rule"""
        rules = [
            {
                "id": "RULE_001",
                "name": "Cell Voltage Deviation",
                "device_types": ["BMS"],
                "condition": {
                    "type": "threshold",
                    "field": "max_delta_v",
                    "operator": ">=",
                    "value": 0.1,
                },
                "severity": "Warning",
                "priority": 5,
                "actions": ["trigger_llm_diagnostic"],
                "metadata": {"alarm_type": "cell_voltage_deviation"},
            }
        ]

        matcher = RuleMatcher(rules)

        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"max_delta_v": 0.15},
        )

        matched = matcher.match(device_data)
        assert len(matched) == 1
        assert matched[0]["rule"]["id"] == "RULE_001"

    def test_match_pcs_rule(self):
        """Test matching PCS rule"""
        rules = [
            {
                "id": "RULE_011",
                "name": "PCS Power Limit Exceeded",
                "device_types": ["PCS"],
                "condition": {
                    "type": "threshold",
                    "field": "active_power",
                    "operator": ">",
                    "value": 1000,
                },
                "severity": "Critical",
                "priority": 9,
                "actions": ["trigger_llm_diagnostic"],
                "metadata": {"alarm_type": "pcs_power_limit_exceeded"},
            }
        ]

        matcher = RuleMatcher(rules)

        device_data = DeviceData(
            device_id="PCS_001",
            device_type=DeviceType.PCS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"active_power": 1200.0},
        )

        matched = matcher.match(device_data)
        assert len(matched) == 1
        assert matched[0]["rule"]["id"] == "RULE_011"

    def test_device_type_filter(self):
        """Test device type filtering"""
        rules = [
            {
                "id": "RULE_BMS",
                "name": "BMS Rule",
                "device_types": ["BMS"],
                "condition": {
                    "type": "threshold",
                    "field": "max_delta_v",
                    "operator": ">=",
                    "value": 0.1,
                },
                "severity": "Warning",
                "priority": 5,
                "actions": [],
                "metadata": {},
            },
            {
                "id": "RULE_PCS",
                "name": "PCS Rule",
                "device_types": ["PCS"],
                "condition": {
                    "type": "threshold",
                    "field": "active_power",
                    "operator": ">",
                    "value": 1000,
                },
                "severity": "Critical",
                "priority": 9,
                "actions": [],
                "metadata": {},
            },
        ]

        matcher = RuleMatcher(rules)

        # BMS device should only match BMS rule
        bms_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"max_delta_v": 0.15},
        )
        matched = matcher.match(bms_data)
        assert len(matched) == 1
        assert matched[0]["rule"]["id"] == "RULE_BMS"

        # PCS device should only match PCS rule
        pcs_data = DeviceData(
            device_id="PCS_001",
            device_type=DeviceType.PCS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"active_power": 1200.0},
        )
        matched = matcher.match(pcs_data)
        assert len(matched) == 1
        assert matched[0]["rule"]["id"] == "RULE_PCS"


class TestRuleEngine:
    """Test rule engine"""

    def test_load_rules_from_file(self):
        """Test loading rules from file"""
        engine = RuleEngine(rules_file="config/rules.yaml")
        rules = engine.get_rules()
        assert len(rules) > 0

    def test_evaluate_bms_data(self):
        """Test evaluating BMS data"""
        rules = [
            {
                "id": "RULE_001",
                "name": "Cell Voltage Deviation",
                "device_types": ["BMS"],
                "condition": {
                    "type": "threshold",
                    "field": "max_delta_v",
                    "operator": ">=",
                    "value": 0.1,
                },
                "severity": "Warning",
                "priority": 5,
                "actions": ["log_alarm"],
                "metadata": {"alarm_type": "cell_voltage_deviation"},
            }
        ]

        engine = RuleEngine(rules=rules)

        # Create BMS data using DeviceData
        bms_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"max_delta_v": 0.15},
        )

        alarms = engine.evaluate(bms_data)
        assert len(alarms) == 1
        assert alarms[0].alarm_type == "cell_voltage_deviation"
        assert alarms[0].severity.value == "Warning"

    def test_evaluate_pcs_data(self):
        """Test evaluating PCS data"""
        rules = [
            {
                "id": "RULE_011",
                "name": "PCS Power Limit Exceeded",
                "device_types": ["PCS"],
                "condition": {
                    "type": "threshold",
                    "field": "active_power",
                    "operator": ">",
                    "value": 1000,
                },
                "severity": "Critical",
                "priority": 9,
                "actions": ["log_alarm"],
                "metadata": {"alarm_type": "pcs_power_limit_exceeded"},
            }
        ]

        engine = RuleEngine(rules=rules)

        # Create PCS data
        pcs_data = PCSData(
            device_id="PCS_001",
            timestamp=datetime.utcnow(),
            active_power=1200.0,
            reactive_power=100.0,
            voltage=400.0,
            current=300.0,
            frequency=50.0,
            efficiency=95.0,
            status="running",
        )

        device_data = pcs_data.to_device_data("test")
        alarms = engine.evaluate(device_data)
        assert len(alarms) == 1
        assert alarms[0].alarm_type == "pcs_power_limit_exceeded"
        assert alarms[0].severity.value == "Critical"

    def test_evaluate_and_execute(self):
        """Test evaluate and execute"""
        rules = [
            {
                "id": "RULE_001",
                "name": "Test Rule",
                "device_types": ["BMS"],
                "condition": {
                    "type": "threshold",
                    "field": "max_delta_v",
                    "operator": ">=",
                    "value": 0.1,
                },
                "severity": "Warning",
                "priority": 5,
                "actions": ["log_alarm"],
                "metadata": {"alarm_type": "test"},
            }
        ]

        engine = RuleEngine(rules=rules)

        device_data = DeviceData(
            device_id="BMS_001",
            device_type=DeviceType.BMS,
            timestamp=datetime.utcnow(),
            source="test",
            data={"max_delta_v": 0.15},
        )

        result = engine.evaluate_and_execute(device_data)
        assert len(result["alarms"]) == 1
        assert len(result["execution_results"]) == 1

    def test_add_remove_rule(self):
        """Test adding and removing rules dynamically"""
        engine = RuleEngine(rules=[])

        new_rule = {
            "id": "RULE_NEW",
            "name": "New Rule",
            "device_types": ["BMS"],
            "condition": {
                "type": "threshold",
                "field": "max_delta_v",
                "operator": ">=",
                "value": 0.1,
            },
            "severity": "Warning",
            "priority": 5,
            "actions": [],
            "metadata": {},
        }

        engine.add_rule(new_rule)
        assert len(engine.get_rules()) == 1

        engine.remove_rule("RULE_NEW")
        assert len(engine.get_rules()) == 0

