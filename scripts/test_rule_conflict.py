#!/usr/bin/env python3
"""
Test script for rule conflict detection
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rule_engine.conflict_detector import RuleConflictDetector, ConflictType

def test_id_duplicate():
    """Test ID duplicate detection"""
    print("Testing ID duplicate detection...")
    
    existing_rules = [
        {
            "id": "RULE_001",
            "name": "Test Rule 1",
            "device_types": ["BMS"],
            "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 50}
        }
    ]
    
    new_rule = {
        "id": "RULE_001",  # Duplicate ID
        "name": "Test Rule 2",
        "device_types": ["BMS"],
        "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 60}
    }
    
    conflicts = RuleConflictDetector.detect_conflicts(new_rule, existing_rules)
    error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
    
    assert len(error_conflicts) > 0, "Should detect ID duplicate"
    assert any(c.get("type") == ConflictType.ID_DUPLICATE for c in error_conflicts), "Should be ID_DUPLICATE type"
    print("✓ ID duplicate detection works")

def test_logical_contradiction():
    """Test logical contradiction detection"""
    print("Testing logical contradiction detection...")
    
    existing_rules = [
        {
            "id": "RULE_001",
            "name": "High Temperature",
            "device_types": ["BMS"],
            "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 50}
        }
    ]
    
    new_rule = {
        "id": "RULE_002",
        "name": "Low Temperature",
        "device_types": ["BMS"],
        "condition": {"type": "threshold", "field": "temperature", "operator": "<", "value": 50}
    }
    
    conflicts = RuleConflictDetector.detect_conflicts(new_rule, existing_rules)
    error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
    
    assert len(error_conflicts) > 0, "Should detect logical contradiction"
    assert any(c.get("type") == ConflictType.LOGICAL_CONTRADICTION for c in error_conflicts), "Should be LOGICAL_CONTRADICTION type"
    print("✓ Logical contradiction detection works")

def test_condition_overlap():
    """Test condition overlap detection"""
    print("Testing condition overlap detection...")
    
    existing_rules = [
        {
            "id": "RULE_001",
            "name": "Temperature Warning",
            "device_types": ["BMS"],
            "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 40}
        }
    ]
    
    new_rule = {
        "id": "RULE_002",
        "name": "Temperature Critical",
        "device_types": ["BMS"],
        "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 45}
    }
    
    conflicts = RuleConflictDetector.detect_conflicts(new_rule, existing_rules)
    warning_conflicts = [c for c in conflicts if c.get("severity") == "warning"]
    
    assert len(warning_conflicts) > 0, "Should detect condition overlap"
    assert any(c.get("type") == ConflictType.CONDITION_OVERLAP for c in warning_conflicts), "Should be CONDITION_OVERLAP type"
    print("✓ Condition overlap detection works")

def test_no_conflict():
    """Test no conflict scenario"""
    print("Testing no conflict scenario...")
    
    existing_rules = [
        {
            "id": "RULE_001",
            "name": "BMS Temperature",
            "device_types": ["BMS"],
            "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 50}
        }
    ]
    
    new_rule = {
        "id": "RULE_002",
        "name": "PCS Temperature",
        "device_types": ["PCS"],  # Different device type
        "condition": {"type": "threshold", "field": "temperature", "operator": ">", "value": 50}
    }
    
    conflicts = RuleConflictDetector.detect_conflicts(new_rule, existing_rules)
    error_conflicts = [c for c in conflicts if c.get("severity") == "error"]
    
    assert len(error_conflicts) == 0, "Should not detect errors for different device types"
    print("✓ No conflict detection works")

if __name__ == "__main__":
    print("Running rule conflict detection tests...\n")
    
    try:
        test_id_duplicate()
        test_logical_contradiction()
        test_condition_overlap()
        test_no_conflict()
        
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
