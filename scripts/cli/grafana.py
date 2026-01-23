"""
Grafana management commands
"""

import os
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
PROJECT_ROOT = Path(__file__).parent.parent.parent
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def print_header(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def get_grafana_client():
    """Get Grafana client configuration"""
    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    api_key = os.getenv("GRAFANA_API_KEY", "")

    if not api_key or api_key == "your_grafana_api_key_here":
        return None, None, None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    return grafana_url, api_key, headers


def create_grafana_key():
    """Create Grafana API Key"""
    if not REQUESTS_AVAILABLE:
        print("✗ Error: requests package not installed")
        print("Please install: pip install requests")
        return False

    print_header("Creating Grafana API Key")

    grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
    print(f"Grafana URL: {grafana_url}\n")

    # Check if Grafana is accessible
    try:
        response = requests.get(f"{grafana_url}/api/health", timeout=5)
        if response.status_code != 200:
            print(
                f"⚠ Warning: Grafana may not be running (status: {response.status_code})"
            )
    except Exception as e:
        print(f"✗ Cannot connect to Grafana: {e}")
        print("Please ensure Grafana is started: cd docker && docker-compose up -d")
        return False

    # Get credentials
    print("Please enter Grafana login information:")
    username = input("Username [admin]: ").strip() or "admin"
    password = getpass("Password: ")

    if not password:
        print("✗ Password cannot be empty")
        return False

    key_name = input("API Key name [bess-agent]: ").strip() or "bess-agent"

    # Create API Key
    url = f"{grafana_url}/api/auth/keys"
    auth = (username, password)
    api_key_data = {"name": key_name, "role": "Admin", "secondsToLive": None}

    try:
        response = requests.post(url, json=api_key_data, auth=auth, timeout=10)
        if response.status_code == 200:
            result = response.json()
            api_key = result.get("key")
            if api_key:
                print("\n✓ API Key created successfully!")
                print(f"Name: {key_name}")
                print(f"API Key: {api_key}")
                print("\nPlease add the following to your .env file:")
                print(f"GRAFANA_API_KEY={api_key}")
                return True
            else:
                print("✗ API Key not found in response")
                return False
        else:
            print(f"✗ Creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def get_datasource_uid(grafana_url, headers):
    """Get InfluxDB datasource UID"""
    try:
        response = requests.get(
            f"{grafana_url}/api/datasources", headers=headers, timeout=10
        )
        if response.status_code == 200:
            for ds in response.json():
                if ds.get("name") == "InfluxDB-BESS":
                    return ds.get("uid")
    except Exception:
        pass
    return None


def create_datasource(grafana_url, headers):
    """Create InfluxDB data source"""
    datasource_config = {
        "name": "InfluxDB-BESS",
        "type": "influxdb",
        "url": "http://influxdb:8086",
        "access": "proxy",
        "isDefault": True,
        "jsonData": {
            "version": "Flux",
            "organization": "bess",
            "defaultBucket": "alarms",
            "tlsSkipVerify": True,
        },
        "secureJsonData": {
            "token": os.getenv("INFLUXDB_TOKEN", ""),
        },
    }

    try:
        response = requests.post(
            f"{grafana_url}/api/datasources",
            json=datasource_config,
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            print("   ✓ Data source created successfully")
            return response.json().get("datasource", {}).get("uid")
        elif response.status_code == 409:
            print("   ⚠ Data source already exists")
            return get_datasource_uid(grafana_url, headers)
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None


def get_dashboard_config(datasource_ref):
    """Get dashboard configuration"""
    return {
        "dashboard": {
            "title": "BESS Alarm Monitoring",
            "tags": ["bess", "alarm"],
            "timezone": "browser",
            "refresh": "10s",
            "time": {"from": "now-24h", "to": "now"},
            "timepicker": {
                "refresh_intervals": [
                    "5s",
                    "10s",
                    "30s",
                    "1m",
                    "5m",
                    "15m",
                    "30m",
                    "1h",
                    "2h",
                    "1d",
                ],
                "time_options": [
                    "5m",
                    "15m",
                    "1h",
                    "6h",
                    "12h",
                    "24h",
                    "2d",
                    "7d",
                    "30d",
                ],
            },
            "liveNow": True,
            "panels": [
                {
                    "id": 1,
                    "title": "SOC Trend",
                    "type": "timeseries",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                    "targets": [
                        {
                            "query": 'from(bucket: "alarms") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "bms_data" and r["metric"] == "soc") |> group(columns: ["metric"]) |> aggregateWindow(every: 5m, fn: mean, createEmpty: false) |> limit(n: 100)',
                            "refId": "A",
                            "datasource": datasource_ref,
                        }
                    ],
                },
                {
                    "id": 2,
                    "title": "Voltage Difference (ΔV)",
                    "type": "timeseries",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                    "targets": [
                        {
                            "query": 'from(bucket: "alarms") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "bms_data" and r["metric"] == "max_delta_v") |> group(columns: ["metric"]) |> aggregateWindow(every: 5m, fn: mean, createEmpty: false) |> limit(n: 100)',
                            "refId": "A",
                            "datasource": datasource_ref,
                        }
                    ],
                },
                {
                    "id": 3,
                    "title": "PCS Active Power",
                    "type": "timeseries",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                    "targets": [
                        {
                            "query": 'from(bucket: "alarms") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "pcs_data" and r["metric"] == "active_power") |> group(columns: ["metric"]) |> aggregateWindow(every: 5m, fn: mean, createEmpty: false) |> limit(n: 100)',
                            "refId": "A",
                            "datasource": datasource_ref,
                        }
                    ],
                },
                {
                    "id": 4,
                    "title": "PCS Efficiency",
                    "type": "timeseries",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                    "targets": [
                        {
                            "query": 'from(bucket: "alarms") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "pcs_data" and r["metric"] == "efficiency") |> group(columns: ["metric"]) |> aggregateWindow(every: 5m, fn: mean, createEmpty: false) |> limit(n: 100)',
                            "refId": "A",
                            "datasource": datasource_ref,
                        }
                    ],
                },
                {
                    "id": 5,
                    "title": "Alarm Statistics",
                    "type": "stat",
                    "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16},
                    "targets": [
                        {
                            "query": 'from(bucket: "alarms") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "alarms") |> group() |> sum(column: "_value")',
                            "refId": "A",
                            "datasource": datasource_ref,
                        }
                    ],
                },
            ],
        },
        "overwrite": True,
    }


def setup_grafana():
    """Setup Grafana (data source and dashboard)"""
    if not REQUESTS_AVAILABLE:
        print("✗ Error: requests package not installed")
        return False

    print_header("Setting up Grafana")

    grafana_url, api_key, headers = get_grafana_client()
    if not headers:
        print("✗ Error: GRAFANA_API_KEY not configured")
        print("Please run: python agent.py create-grafana-key")
        return False

    # Create data source
    print("1. Creating InfluxDB data source...")
    ds_uid = create_datasource(grafana_url, headers)
    if ds_uid is None:
        return False

    # Create dashboard
    print("\n2. Creating Dashboard...")
    datasource_ref = (
        {"type": "influxdb", "uid": ds_uid}
        if ds_uid
        else {"type": "influxdb", "name": "InfluxDB-BESS"}
    )

    dashboard_config = get_dashboard_config(datasource_ref)

    try:
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            json=dashboard_config,
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            print("   ✓ Dashboard created successfully")
            print("\n✓ Setup completed!")
            print(f"Access Grafana: {grafana_url}")
            return True
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def check_grafana():
    """Check Grafana configuration"""
    if not REQUESTS_AVAILABLE:
        print("✗ Error: requests package not installed")
        return False

    print_header("Checking Grafana Configuration")

    grafana_url, api_key, headers = get_grafana_client()
    if not headers:
        print("✗ Error: GRAFANA_API_KEY not configured")
        return False

    print(f"Grafana URL: {grafana_url}\n")

    # Check data sources
    print("1. Checking data sources...")
    try:
        response = requests.get(
            f"{grafana_url}/api/datasources", headers=headers, timeout=10
        )
        if response.status_code == 200:
            datasources = response.json()
            if datasources:
                print(f"   ✓ Found {len(datasources)} data source(s):")
                for ds in datasources:
                    print(f"      - {ds.get('name')} ({ds.get('type')})")
                    test_url = f"{grafana_url}/api/datasources/{ds['id']}/health"
                    test_resp = requests.get(test_url, headers=headers, timeout=10)
                    if test_resp.status_code == 200:
                        print("        ✓ Connection OK")
                    else:
                        print(f"        ✗ Connection failed: {test_resp.status_code}")
            else:
                print("   ⚠ No data sources found")
        else:
            print(f"   ✗ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Check dashboards
    print("\n2. Checking dashboards...")
    try:
        response = requests.get(
            f"{grafana_url}/api/search?query=BESS", headers=headers, timeout=10
        )
        if response.status_code == 200:
            dashboards = response.json()
            if dashboards:
                print(f"   ✓ Found {len(dashboards)} dashboard(s):")
                for db in dashboards:
                    print(f"      - {db.get('title')} (ID: {db.get('id')})")
            else:
                print("   ⚠ No dashboards found")
        else:
            print(f"   ✗ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    return True


def fix_grafana():
    """Fix Grafana datasource references"""
    if not REQUESTS_AVAILABLE:
        print("✗ Error: requests package not installed")
        return False

    print_header("Fixing Grafana Datasource References")

    grafana_url, api_key, headers = get_grafana_client()
    if not headers:
        print("✗ Error: GRAFANA_API_KEY not configured")
        return False

    # Get datasource UID
    print("1. Getting datasource information...")
    ds_uid = get_datasource_uid(grafana_url, headers)
    if not ds_uid:
        print("   ✗ InfluxDB-BESS datasource not found")
        return False
    print(f"   ✓ Found datasource: InfluxDB-BESS (UID: {ds_uid})")

    # Get dashboard
    print("\n2. Getting dashboard...")
    try:
        response = requests.get(
            f"{grafana_url}/api/search?query=BESS", headers=headers, timeout=10
        )
        if response.status_code == 200:
            dashboards = response.json()
            if not dashboards:
                print("   ✗ No dashboard found")
                return False

            dashboard_uid = dashboards[0].get("uid")
            print(f"   ✓ Found dashboard: {dashboards[0].get('title')}")
        else:
            print(f"   ✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Get dashboard details and fix
    print("\n3. Fixing datasource references...")
    try:
        response = requests.get(
            f"{grafana_url}/api/dashboards/uid/{dashboard_uid}",
            headers=headers,
            timeout=10,
        )
        if response.status_code == 200:
            dashboard_data = response.json()
            dashboard_json = dashboard_data.get("dashboard", {})

            fixed = False

            def fix_panel(panel):
                nonlocal fixed
                if "targets" in panel:
                    for target in panel.get("targets", []):
                        if "datasource" in target:
                            target["datasource"] = {"type": "influxdb", "uid": ds_uid}
                            fixed = True
                if "panels" in panel:
                    for sub_panel in panel["panels"]:
                        fix_panel(sub_panel)

            if "panels" in dashboard_json:
                for panel in dashboard_json["panels"]:
                    fix_panel(panel)

            if not fixed:
                print("   ⚠ No datasource references found to fix")
                return True

            # Update dashboard
            update_data = {"dashboard": dashboard_json, "overwrite": True}
            response = requests.post(
                f"{grafana_url}/api/dashboards/db",
                json=update_data,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                print("   ✓ Dashboard updated successfully")
                print(f"\n✓ Fix completed! Please refresh Grafana: {grafana_url}")
                return True
            else:
                print(f"   ✗ Update failed: {response.status_code}")
                return False
        else:
            print(f"   ✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
