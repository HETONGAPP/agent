#!/usr/bin/env python3
"""
Test SOC high rule matching and alarm generation
"""

import os
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from src.core.database import Database
from src.storage.postgresql_metadata import PostgreSQLMetadataStorage
from src.models.device_data import DeviceData, DeviceType
from src.rule_engine.engine import RuleEngine
from src.agent.dependencies import get_site_manager
from src.agent.app_setup import get_app_state

def test_soc_rule():
    """Test SOC high rule"""
    print("=== Testing SOC High Rule ===\n")
    
    # Get rule from database
    db = Database()
    postgres_storage = PostgreSQLMetadataStorage(db)
    
    site_id = "CANADA_SITE_1"
    rules = postgres_storage.get_rules_by_site(site_id, enabled_only=False)
    soc_rule = next((r for r in rules if 'soc' in r.get('name', '').lower() and 'high' in r.get('name', '').lower()), None)
    
    if not soc_rule:
        print("❌ SOC high rule not found in database")
        return
    
    print(f"Rule: {soc_rule.get('id')}")
    print(f"  Name: {soc_rule.get('name')}")
    print(f"  Enabled: {soc_rule.get('enabled', True)}")
    condition = soc_rule.get('condition', {})
    print(f"  Condition: {condition.get('field')} {condition.get('operator')} {condition.get('value')}")
    print(f"  Device IDs: {soc_rule.get('device_ids', [])}")
    print()
    
    # Create test device data
    device_data = DeviceData(
        device_id="BMS_001",
        device_type=DeviceType.BMS,
        timestamp=datetime.now(UTC),
        source="test",
        site_id=site_id,
        data={
            "soc": 81.0,  # Should trigger if threshold is 50%
            "soh": 95.0,
            "max_delta_v": 0.05,
            "max_temperature": 30.0,
            "min_temperature": 25.0,
        }
    )
    
    print(f"Test Device Data:")
    print(f"  Device ID: {device_data.device_id}")
    print(f"  Device Type: {device_data.device_type.value}")
    print(f"  Site ID: {device_data.site_id}")
    print(f"  SOC: {device_data.data.get('soc')}%")
    print(f"  Available fields: {list(device_data.data.keys())}")
    print()
    
    # Test rule matching
    print("=== Testing Rule Matching ===")
    
    # Check if rule is applicable
    from src.rule_engine.matcher import RuleMatcher
    matcher = RuleMatcher([soc_rule])
    
    applicable = matcher._is_rule_applicable(soc_rule, device_data)
    print(f"Rule applicable: {applicable}")
    
    if not applicable:
        print("❌ Rule is not applicable to device data")
        rule_device_ids = soc_rule.get("device_ids", [])
        rule_device_types = soc_rule.get("device_types", [])
        print(f"  Device ID match: {device_data.device_id} in {rule_device_ids} = {device_data.device_id in rule_device_ids}")
        print(f"  Device Type match: {device_data.device_type.value} in {rule_device_types} = {device_data.device_type.value in rule_device_types}")
        
        condition = soc_rule.get("condition", {})
        field_path = condition.get("field")
        has_field = device_data.has_field(field_path) if field_path else False
        print(f"  Field exists: {field_path} = {has_field}")
        if field_path:
            field_value = device_data.get_field(field_path)
            print(f"  Field value: {field_path} = {field_value}")
        return
    
    # Test condition evaluation
    print("\n=== Testing Condition Evaluation ===")
    from src.rule_engine.conditions import ConditionEvaluator
    condition = soc_rule.get("condition", {})
    result = ConditionEvaluator.evaluate(condition, device_data)
    print(f"Condition result: {result}")
    
    field_path = condition.get("field")
    operator = condition.get("operator")
    threshold = condition.get("value")
    field_value = device_data.get_field(field_path)
    print(f"  {field_path} ({field_value}) {operator} {threshold} = {result}")
    
    # Test full rule matching
    print("\n=== Testing Full Rule Matching ===")
    matched_rules = matcher.match(device_data)
    print(f"Matched rules: {len(matched_rules)}")
    for matched in matched_rules:
        rule = matched["rule"]
        print(f"  - {rule.get('id')}: {rule.get('name')}")
    
    # Test alarm generation
    if matched_rules:
        print("\n=== Testing Alarm Generation ===")
        alarm = matcher.create_alarm(matched_rules[0])
        print(f"Alarm ID: {alarm.alarm_id}")
        print(f"  Rule ID: {alarm.metadata.get('rule_id')}")
        print(f"  Alarm Type: {alarm.alarm_type}")
        print(f"  Severity: {alarm.severity}")
        print(f"  Device ID: {alarm.metadata.get('device_id')}")
    else:
        print("❌ No rules matched, cannot generate alarm")

if __name__ == '__main__':
    test_soc_rule()


