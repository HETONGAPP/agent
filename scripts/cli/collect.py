"""
Data collection commands
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Import after path setup
from src.collector.mock_collector import MockCollector  # noqa: E402
from src.storage.influxdb_client import InfluxDBClient  # noqa: E402


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def collect_data():
    """Run data collection"""
    print_header("Running Data Collection")

    async def run_collection():
        collector = MockCollector(source="BMS")

        influx_url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        influx_token = os.getenv("INFLUXDB_TOKEN", "")
        influx_org = os.getenv("INFLUXDB_ORG", "bess")
        influx_bucket = os.getenv("INFLUXDB_BUCKET", "alarms")

        if not influx_token:
            print("✗ Error: INFLUXDB_TOKEN not configured")
            return False

        try:
            influx_client = InfluxDBClient(
                url=influx_url,
                token=influx_token,
                org=influx_org,
                bucket=influx_bucket,
            )
            print(f"✓ Connected to InfluxDB: {influx_url}")
        except Exception as e:
            print(f"✗ InfluxDB connection failed: {e}")
            return False

        interval = int(os.getenv("COLLECT_INTERVAL", "30"))
        print(f"Starting data collection, interval: {interval} seconds")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                alarms = await collector.collect_alarms()
                print(f"Collected {len(alarms)} alarms")

                for pack_id in ["PACK_001", "PACK_002", "PACK_003"]:
                    bms_data = await collector.get_bms_data(pack_id)
                    influx_client.write_bms_data(bms_data)
                    print(
                        f"Written BMS data: {pack_id} - SOC: {bms_data.soc}%, ΔV: {bms_data.max_delta_v}V"
                    )

                for alarm in alarms:
                    influx_client.write_alarm(alarm)
                    print(f"Written alarm: {alarm.alarm_id} - {alarm.alarm_type}")

                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopping collection...")
        finally:
            influx_client.close()
            print("Connection closed")

        return True

    return asyncio.run(run_collection())
