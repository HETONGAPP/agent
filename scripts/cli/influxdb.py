"""
InfluxDB management commands
"""

import os
import zoneinfo
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
PROJECT_ROOT = Path(__file__).parent.parent.parent
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

try:
    from influxdb_client import InfluxDBClient

    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False

# Montreal timezone (EST/EDT, UTC-5 or UTC-4)
MONTREAL_TZ = zoneinfo.ZoneInfo("America/Montreal")


def to_montreal_time(utc_time):
    """Convert UTC datetime to Montreal time (EST/EDT)"""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    elif utc_time.tzinfo != timezone.utc:
        utc_time = utc_time.astimezone(timezone.utc)
    return utc_time.astimezone(MONTREAL_TZ)


def format_time_display(utc_time, show_utc=False):
    """Format time for display in Montreal timezone"""
    montreal_time = to_montreal_time(utc_time)
    tz_name = "EST" if montreal_time.dst() is None else "EDT"
    if show_utc:
        return f"{montreal_time.strftime('%Y-%m-%d %H:%M:%S')} {tz_name} (UTC: {utc_time.strftime('%Y-%m-%d %H:%M:%S')})"
    return f"{montreal_time.strftime('%Y-%m-%d %H:%M:%S')} {tz_name}"


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_influxdb():
    """Check InfluxDB data"""
    if not INFLUXDB_AVAILABLE:
        print("✗ Error: influxdb-client package not installed")
        print("Please install: pip install influxdb-client")
        return False

    print_header("Checking InfluxDB Data")

    url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
    token = os.getenv("INFLUXDB_TOKEN", "")
    org = os.getenv("INFLUXDB_ORG", "bess")
    bucket = os.getenv("INFLUXDB_BUCKET", "alarms")

    if not token:
        print("✗ Error: INFLUXDB_TOKEN not configured")
        return False

    print(f"InfluxDB URL: {url}")
    print(f"Organization: {org}")
    print(f"Bucket: {bucket}\n")

    try:
        client = InfluxDBClient(url=url, token=token, org=org)
        query_api = client.query_api()

        # Query device data (new flexible format) - SOC data in last 1 hour
        print("1. Querying SOC data (last 1 hour)...")
        query = f"""
        from(bucket: "{bucket}")
          |> range(start: -1h)
          |> filter(fn: (r) => r["_measurement"] == "device_data")
          |> filter(fn: (r) => r["device_type"] == "BMS")
          |> filter(fn: (r) => r["metric"] == "soc")
        """

        result = query_api.query(query=query)
        count = 0
        device_ids = set()
        for table in result:
            for record in table.records:
                count += 1
                if hasattr(record, "values") and "device_id" in record.values:
                    device_ids.add(record.values["device_id"])

        if count == 0:
            print("   ⚠ No SOC data found in last 1 hour")
            print("   Trying last 24 hours...")
            # Try last 24 hours
            query_24h = f"""
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "device_data")
              |> filter(fn: (r) => r["device_type"] == "BMS")
              |> filter(fn: (r) => r["metric"] == "soc")
            """
            result_24h = query_api.query(query=query_24h)
            count_24h = 0
            for table in result_24h:
                for record in table.records:
                    count_24h += 1
                    if hasattr(record, "values") and "device_id" in record.values:
                        device_ids.add(record.values["device_id"])
            if count_24h > 0:
                print(f"   ✓ Found {count_24h} SOC data records in last 24 hours")
                if device_ids:
                    print(f"   Devices: {', '.join(sorted(device_ids))}")
            else:
                print("   ⚠ No SOC data found in last 24 hours either")
                # Also check legacy format
                print("   Checking legacy bms_data format...")
                query_legacy = f"""
                from(bucket: "{bucket}")
                  |> range(start: -24h)
                  |> filter(fn: (r) => r["_measurement"] == "bms_data")
                  |> filter(fn: (r) => r["metric"] == "soc")
                """
                result_legacy = query_api.query(query=query_legacy)
                count_legacy = 0
                for table in result_legacy:
                    for record in table.records:
                        count_legacy += 1
                if count_legacy > 0:
                    print(f"   ✓ Found {count_legacy} legacy bms_data records")
                else:
                    print("   ⚠ No data found in any format")
        else:
            print(f"   ✓ Found {count} SOC data records in last 1 hour")
            if device_ids:
                print(f"   Devices: {', '.join(sorted(device_ids))}")

        # Query all BMS device data metrics
        print("\n2. Querying all BMS device data (last 1 hour)...")
        query_all = f"""
        from(bucket: "{bucket}")
          |> range(start: -1h)
          |> filter(fn: (r) => r["_measurement"] == "device_data")
          |> filter(fn: (r) => r["device_type"] == "BMS")
        """
        result_all = query_api.query(query=query_all)
        count_all = 0
        metrics = set()
        latest_time = None
        for table in result_all:
            for record in table.records:
                count_all += 1
                if hasattr(record, "values") and "metric" in record.values:
                    metrics.add(record.values["metric"])
                if hasattr(record, "get_time") and record.get_time():
                    if latest_time is None or record.get_time() > latest_time:
                        latest_time = record.get_time()

        if count_all > 0:
            print(f"   ✓ Found {count_all} total BMS device data records")
            if metrics:
                print(f"   Available metrics: {', '.join(sorted(metrics))}")
            if latest_time:
                if isinstance(latest_time, datetime):
                    montreal_time = format_time_display(latest_time)
                    print(f"   Latest data time: {montreal_time}")
        else:
            print("   ⚠ No BMS device data found in last 1 hour")
            # Check when was the last data written
            print("   Checking last data timestamp...")
            query_last = f"""
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "device_data")
              |> filter(fn: (r) => r["device_type"] == "BMS")
              |> filter(fn: (r) => r["metric"] == "soc")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 1)
            """
            result_last = query_api.query(query=query_last)
            for table in result_last:
                for record in table.records:
                    if hasattr(record, "get_time") and record.get_time():
                        last_time = record.get_time()
                        if isinstance(last_time, datetime):
                            now = datetime.now(timezone.utc)
                            if last_time.tzinfo is None:
                                last_time = last_time.replace(tzinfo=timezone.utc)
                            age = now - last_time
                            hours_ago = age.total_seconds() / 3600
                            montreal_time = format_time_display(last_time)
                            print(
                                f"   Last SOC data: {montreal_time} ({hours_ago:.1f} hours ago)"
                            )
                            if hours_ago > 1:
                                print(
                                    "   ⚠ Data is older than 1 hour. Check if simulator is running."
                                )

        # Query alarm data
        print("\n3. Querying alarm data (last 1 hour)...")
        query = f"""
        from(bucket: "{bucket}")
          |> range(start: -1h)
          |> filter(fn: (r) => r["_measurement"] == "alarms")
        """

        result = query_api.query(query=query)
        count = 0
        for table in result:
            for record in table.records:
                count += 1

        if count == 0:
            print("   ⚠ No alarm data found in last 1 hour")
            # Try last 24 hours
            query_24h = f"""
            from(bucket: "{bucket}")
              |> range(start: -24h)
              |> filter(fn: (r) => r["_measurement"] == "alarms")
            """
            result_24h = query_api.query(query=query_24h)
            count_24h = 0
            for table in result_24h:
                for record in table.records:
                    count_24h += 1
            if count_24h > 0:
                print(f"   ✓ Found {count_24h} alarm data records in last 24 hours")
            else:
                print("   ⚠ No alarm data found")
        else:
            print(f"   ✓ Found {count} alarm data records in last 1 hour")

        client.close()
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
