"""
Status checking commands
"""

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
PROJECT_ROOT = Path(__file__).parent.parent.parent
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

from .grafana import check_grafana  # noqa: E402
from .influxdb import check_influxdb  # noqa: E402
from .service import get_current_port  # noqa: E402

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


def check_emqx():
    """Check EMQX (MQTT Broker) status"""
    print("   Checking EMQX service...")

    # Check Docker container
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=bess-emqx", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            status = result.stdout.strip()
            print(f"   ✓ EMQX container: {status}")
        else:
            print("   ⚠ EMQX container not running")
            print("      Start with: cd docker && docker-compose up -d emqx")
            return False
    except Exception as e:
        print(f"   ⚠ Cannot check Docker: {e}")
        return False

    # Check MQTT broker connection
    mqtt_broker_url = os.getenv("MQTT_BROKER_URL", "")
    if mqtt_broker_url:
        print(f"   MQTT Broker URL: {mqtt_broker_url}")

        # Try to check if Agent is connected to MQTT
        if REQUESTS_AVAILABLE:
            current_port = get_current_port()
            ports_to_try = (
                [current_port] if current_port else [8000, 8001, 8002, 8003, 8004, 8005]
            )

            for port in ports_to_try:
                try:
                    response = requests.get(
                        f"http://localhost:{port}/health", timeout=2
                    )
                    if response.status_code == 200:
                        data = response.json()
                        mqtt_status = data.get("mqtt_connected", False)
                        if mqtt_status:
                            print("   ✓ Agent connected to MQTT broker")
                        else:
                            print("   ⚠ Agent not connected to MQTT broker")
                        break
                except Exception:
                    continue
    else:
        print("   ℹ MQTT_BROKER_URL not configured")
        print("      Configure in .env: MQTT_BROKER_URL=mqtt://localhost:1883")

    # Check EMQX Dashboard
    try:
        emqx_dashboard_url = "http://localhost:18083"
        response = requests.get(f"{emqx_dashboard_url}/api/v5/status", timeout=2)
        if response.status_code == 200:
            print(f"   ✓ EMQX Dashboard accessible: {emqx_dashboard_url}")
        else:
            print(
                f"   ⚠ EMQX Dashboard not accessible (status: {response.status_code})"
            )
    except Exception:
        print("   ⚠ EMQX Dashboard not accessible (may not be running)")

    return True


def check_status():
    """Check system health status"""
    print_header("System Health Check")

    # Check Docker services
    print("1. Checking Docker services...")
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            services = [
                line
                for line in result.stdout.split("\n")
                if any(
                    s in line
                    for s in [
                        "influxdb",
                        "grafana",
                        "postgres",
                        "redis",
                        "emqx",
                        "agent",
                    ]
                )
            ]
            if services:
                for service in services:
                    print(f"   {service}")
            else:
                print("   ⚠ No services found")
        else:
            print("   ⚠ Docker not available or no services running")
    except Exception as e:
        print(f"   ⚠ Cannot check Docker: {e}")

    # Check Agent service
    print("\n2. Checking Agent service...")
    if REQUESTS_AVAILABLE:
        current_port = get_current_port()

        ports_to_try = []
        if current_port:
            ports_to_try.append(current_port)

        default_port = (
            int(os.getenv("AGENT_URL", "http://localhost:8000").split(":")[-1])
            if ":" in os.getenv("AGENT_URL", "")
            else 8000
        )
        for port in [default_port, 8001, 8002, 8003, 8004, 8005]:
            if port not in ports_to_try:
                ports_to_try.append(port)

        agent_found = False
        for port in ports_to_try:
            agent_url = f"http://localhost:{port}"
            try:
                response = requests.get(f"{agent_url}/health", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✓ Agent service running on port {port}")
                    print(f"      URL: {agent_url}")
                    print(f"      Status: {data.get('status')}")
                    print(
                        f"      InfluxDB connected: {data.get('influxdb_connected', False)}"
                    )
                    print(f"      MQTT connected: {data.get('mqtt_connected', False)}")
                    agent_found = True
                    break
            except Exception:
                continue

        if not agent_found:
            print("   ⚠ Agent service not found on any checked port")
            print(f"      Checked ports: {', '.join(map(str, ports_to_try[:5]))}")
            print("      Try starting the service: python scripts/agent.py start")
    else:
        print("   ⚠ Cannot check (requests not installed)")

    # Check EMQX/MQTT
    print("\n3. Checking EMQX (MQTT Broker)...")
    check_emqx()

    # Check Grafana
    print("\n4. Checking Grafana...")
    check_grafana()

    # Check InfluxDB data
    print("\n5. Checking InfluxDB data...")
    check_influxdb()

    return True
