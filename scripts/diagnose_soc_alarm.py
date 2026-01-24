#!/usr/bin/env python3
"""
Diagnose why SOC high alarm is not triggering
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

def diagnose_soc_alarm():
    """Diagnose SOC high alarm issue"""
    print("=== Diagnosing SOC High Alarm Issue ===\n")
    
    # Check database rules
    db = Database()
    postgres_storage = PostgreSQLMetadataStorage(db)
    
    sites = postgres_storage.get_all_sites()
    print(f"Found {len(sites)} sites\n")
    
    for site in sites:
        site_id = site.get('site_id')
        print(f"=== Site: {site_id} ===")
        
        # Get SOC high rule
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
                
                print(f"\nRule: {rule_id}")
                print(f"  Name: {name}")
                print(f"  Enabled: {enabled}")
                print(f"  Condition: {field} {operator} {value}")
                print(f"  Device IDs: {device_ids}")
                
                if not enabled:
                    print(f"  ⚠️  Rule is DISABLED!")
        else:
            print("  ❌ No SOC high rule found in database")
            print("  Rules are likely loaded from file (config/rules_universal.yaml)")
            print("  File rule threshold: 95%")
        
        # Check recent alarms
        print(f"\n--- Recent Alarms for Site {site_id} ---")
        url = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
        token = os.getenv('INFLUXDB_TOKEN', '')
        org = os.getenv('INFLUXDB_ORG', 'bess')
        
        client = InfluxDBClient(url=url, token=token, org=org)
        query_api = client.query_api()
        
        bucket = f"site_{site_id}"
        try:
            query = f'''
            from(bucket: "{bucket}")
              |> range(start: -1h)
              |> filter(fn: (r) => r["_measurement"] == "alarms")
              |> filter(fn: (r) => r["alarm_type"] == "soc_high")
              |> limit(n: 10)
            '''
            
            result = query_api.query(query=query)
            alarm_count = 0
            for table in result:
                for record in table.records:
                    alarm_count += 1
                    print(f"  Alarm: {record.values.get('alarm_id', 'N/A')}")
                    print(f"    Type: {record.values.get('alarm_type', 'N/A')}")
                    print(f"    Rule: {record.values.get('rule_id', 'N/A')}")
                    print(f"    Device: {record.values.get('device_id', 'N/A')}")
                    print(f"    Time: {record.get_time()}")
            
            if alarm_count == 0:
                print("  ❌ No SOC high alarms found in last hour")
        except Exception as e:
            print(f"  ⚠️  Error querying alarms: {e}")
        
        # Check recent device data
        print(f"\n--- Recent Device Data for Site {site_id} ---")
        try:
            query = f'''
            from(bucket: "{bucket}")
              |> range(start: -10m)
              |> filter(fn: (r) => r["_measurement"] == "device_data")
              |> filter(fn: (r) => r["device_type"] == "BMS")
              |> filter(fn: (r) => r["_field"] == "soc")
              |> limit(n: 5)
            '''
            
            result = query_api.query(query=query)
            data_count = 0
            for table in result:
                for record in table.records:
                    data_count += 1
                    soc_value = record.get_value()
                    device_id = record.values.get('device_id', 'N/A')
                    print(f"  Device: {device_id}, SOC: {soc_value}%, Time: {record.get_time()}")
            
            if data_count == 0:
                print("  ⚠️  No recent BMS device data found")
        except Exception as e:
            print(f"  ⚠️  Error querying device data: {e}")
        
        client.close()
        print()

if __name__ == '__main__':
    diagnose_soc_alarm()

