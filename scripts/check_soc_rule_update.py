#!/usr/bin/env python3
"""
Check if SOC high rule threshold update is working
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from src.core.database import Database
from src.storage.postgresql_metadata import PostgreSQLMetadataStorage
from influxdb_client import InfluxDBClient
from datetime import datetime, UTC

def check_soc_rule():
    """Check SOC high rule threshold"""
    print("=== Checking SOC High Rule Threshold ===\n")
    
    site_id = "CANADA_SITE_1"
    
    # Check database rules
    try:
        db = Database()
        postgres_storage = PostgreSQLMetadataStorage(db)
        
        rules = postgres_storage.get_rules_by_site(site_id, enabled_only=False)
        soc_rules = [r for r in rules if 'soc' in r.get('name', '').lower() and 'high' in r.get('name', '').lower()]
        
        if soc_rules:
            for rule in soc_rules:
                rule_id = rule.get('id')
                name = rule.get('name')
                enabled = rule.get('enabled', True)
                condition = rule.get('condition', {})
                value = condition.get('value')
                operator = condition.get('operator')
                field = condition.get('field')
                device_ids = rule.get('device_ids', [])
                
                print(f"Rule: {rule_id}")
                print(f"  Name: {name}")
                print(f"  Enabled: {enabled}")
                print(f"  Condition: {field} {operator} {value}")
                print(f"  Device IDs: {device_ids}")
                print()
        else:
            print("❌ No SOC high rule found in database")
            print("  Rules might be loaded from file (config/rules_universal.yaml)")
            print("  File rule threshold: 95%")
            print()
    except Exception as e:
        print(f"⚠️  Error checking database: {e}")
        print()
    
    # Check recent device data
    print("=== Recent Device Data ===")
    url = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
    token = os.getenv('INFLUXDB_TOKEN', '')
    org = os.getenv('INFLUXDB_ORG', 'bess')
    
    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()
    
    bucket = f"site_{site_id}"
    try:
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -10m)
          |> filter(fn: (r) => r["_measurement"] == "device_data")
          |> filter(fn: (r) => r["device_type"] == "BMS")
          |> filter(fn: (r) => r["_field"] == "soc")
          |> limit(n: 5)
          |> sort(columns: ["_time"], desc: true)
        '''
        
        result = query_api.query(query=query)
        data_count = 0
        for table in result:
            for record in table.records:
                data_count += 1
                soc_value = record.get_value()
                device_id = record.values.get('device_id', 'N/A')
                time = record.get_time()
                print(f"  Device: {device_id}, SOC: {soc_value}%, Time: {time}")
                
                # Check if SOC > 50 (new threshold)
                if soc_value and float(soc_value) > 50:
                    print(f"    ✓ SOC ({soc_value}%) > 50% threshold - Should trigger alarm!")
                else:
                    print(f"    ✗ SOC ({soc_value}%) <= 50% threshold - Will not trigger alarm")
        
        if data_count == 0:
            print("  ⚠️  No recent BMS device data found")
    except Exception as e:
        print(f"  ⚠️  Error querying device data: {e}")
    
    # Check recent alarms
    print("\n=== Recent SOC High Alarms ===")
    try:
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -10m)
          |> filter(fn: (r) => r["_measurement"] == "alarms")
          |> filter(fn: (r) => r["alarm_type"] == "soc_high")
          |> limit(n: 5)
          |> sort(columns: ["_time"], desc: true)
        '''
        
        result = query_api.query(query=query)
        alarm_count = 0
        for table in result:
            for record in table.records:
                alarm_count += 1
                alarm_id = record.values.get('alarm_id', 'N/A')
                device_id = record.values.get('device_id', 'N/A')
                time = record.get_time()
                print(f"  Alarm: {alarm_id}")
                print(f"    Device: {device_id}, Time: {time}")
        
        if alarm_count == 0:
            print("  ❌ No SOC high alarms found in last 10 minutes")
    except Exception as e:
        print(f"  ⚠️  Error querying alarms: {e}")
    
    client.close()
    
    print("\n=== Recommendations ===")
    print("1. Check if rule threshold was updated in database (should be 50)")
    print("2. Check if rule cache was cleared after update")
    print("3. Check if device SOC value is > 50%")
    print("4. Check if rule is enabled")
    print("5. Check if device_id matches rule's device_ids filter")

if __name__ == '__main__':
    check_soc_rule()


